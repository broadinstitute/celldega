import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { global_base_url } from '../global_variables/global_base_url.js'
import { deck_ist } from './deck_ist.js'
import { update_path_layer } from './path_layer.js'
import { update_trx_layer } from './trx_layer.js'
import { layers_ist, update_layers_ist } from './layers_ist.js'
import { landscape_parameters } from '../global_variables/landscape_parameters.js'
import { set_close_up } from '../global_variables/close_up.js'
import { svg_bar_gene, update_bar_graph } from '../ui/bar_plot.js'
import { gene_color_dict } from '../global_variables/gene_color_dict.js'
import { gene_counts } from '../global_variables/meta_gene.js'
import { bar_gene_callback, svg_bar_cluster, bar_cluster_callback } from '../ui/bar_plot.js'
import { trx_combo_data } from '../vector_tile/transcripts/grab_trx_tiles_in_view.js'
import { cell_combo_data } from './cell_layer.js'
import { cluster_color_dict, cluster_counts } from '../global_variables/meta_cluster.js'

export let minX
export let maxX
export let minY
export let maxY

export const calc_viewport = async ({ height, width, zoom, target }) => {
    const tile_size = landscape_parameters.tile_size
    const max_tiles_to_view = 50
    const zoomFactor = Math.pow(2, zoom)
    const [targetX, targetY] = target
    const halfWidthZoomed = width / (2 * zoomFactor)
    const halfHeightZoomed = height / (2 * zoomFactor)

    minX = targetX - halfWidthZoomed
    maxX = targetX + halfWidthZoomed
    minY = targetY - halfHeightZoomed
    maxY = targetY + halfHeightZoomed

    // Get the current viewport from Deck.gl
    const viewports = deck_ist.viewManager.getViewports()
    if (!viewports || viewports.length === 0) {
        // console.error('No viewports available')
        return
    }

    const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tile_size)

    if (tiles_in_view.length < max_tiles_to_view) {
        await update_trx_layer(global_base_url, tiles_in_view)
        await update_path_layer(global_base_url, tiles_in_view)

        set_close_up(true)
        update_layers_ist()

        // gene bar graph update
        const filtered_transcripts = trx_combo_data.filter(pos =>
            pos.x >= minX && pos.x <= maxX && pos.y >= minY && pos.y <= maxY
        );

        const filtered_gene_names = filtered_transcripts.map(transcript => transcript.name);

        const new_bar_data = filtered_gene_names.reduce((acc, gene) => {
            const existingGene = acc.find(item => item.name === gene)
            if (existingGene) {
                existingGene.value += 1
            } else {
                acc.push({ name: gene, value: 1 })
            }
            return acc
        }, []).filter(item => item.value > 0)
        .sort((a, b) => b.value - a.value)

        update_bar_graph(svg_bar_gene, new_bar_data, gene_color_dict, bar_gene_callback)

        // console.log('cell_scatter_data', cell_scatter_data)

        // cell bar graph update
        const filtered_cells = cell_combo_data.filter(pos =>
            pos.x >= minX && pos.x <= maxX && pos.y >= minY && pos.y <= maxY
        );

        const filtered_cell_names = filtered_cells.map(cell => cell.name);

        const new_bar_data_cell = filtered_cell_names.reduce((acc, gene) => {
            const existingGene = acc.find(item => item.name === gene)
            if (existingGene) {
                existingGene.value += 1
            } else {
                acc.push({ name: gene, value: 1 })
            }
            return acc
        }, []).filter(item => item.value > 0)
        .sort((a, b) => b.value - a.value)

        // console.log(new_bar_data_cell)

        update_bar_graph(svg_bar_cluster, new_bar_data_cell, cluster_color_dict, bar_cluster_callback)


    } else {
        set_close_up(false)
        update_layers_ist()
        update_bar_graph(svg_bar_gene, gene_counts, gene_color_dict, bar_gene_callback)
        update_bar_graph(svg_bar_cluster, cluster_counts, cluster_color_dict, bar_cluster_callback)
    }

    deck_ist.setProps({ layers: layers_ist })
}
