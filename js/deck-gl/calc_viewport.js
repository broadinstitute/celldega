import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { global_base_url } from '../global_variables/global_base_url.js'
import { update_path_layer_data } from './path_layer.js'
import { update_trx_layer } from './trx_layer.js'
import { update_layers_ist, get_layers_list } from './layers_ist.js'
import { landscape_parameters } from '../global_variables/landscape_parameters.js'
import { close_up, set_close_up } from '../global_variables/close_up.js'
import { svg_bar_gene, update_bar_graph, bar_container_gene, bar_container_cluster } from '../ui/bar_plot.js'
import { color_dict_gene } from '../global_variables/color_dict_gene.js'
import { gene_counts } from '../global_variables/meta_gene.js'
import { bar_callback_gene, svg_bar_cluster, bar_callback_cluster } from '../ui/bar_plot.js'
import { trx_combo_data } from '../vector_tile/transcripts/grab_trx_tiles_in_view.js'
import { cell_combo_data } from './cell_layer.js'
import { color_dict_cluster, cluster_counts } from '../global_variables/meta_cluster.js'
import { selected_cats } from '../global_variables/cat.js'
import { selected_genes } from '../global_variables/selected_genes.js'

export let minX
export let maxX
export let minY
export let maxY

export const calc_viewport = async ({ height, width, zoom, target }, deck_ist, layers_obj) => {

    console.log('calc_viewport')
    console.log('layers_obj', layers_obj)

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
        console.error('No viewports available')
        return
    }

    const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tile_size)

    if (tiles_in_view.length < max_tiles_to_view) {

        await update_trx_layer(global_base_url, tiles_in_view)

        await update_path_layer_data(global_base_url, tiles_in_view, layers_obj)

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

        update_bar_graph(svg_bar_gene, new_bar_data, color_dict_gene, bar_callback_gene, selected_genes, deck_ist)

        bar_container_gene.scrollTo({
            top: 0,
            behavior: 'smooth'
        })

        // cell bar graph update
        const filtered_cells = cell_combo_data.filter(pos =>
            pos.x >= minX && pos.x <= maxX && pos.y >= minY && pos.y <= maxY
        )

        const filtered_cell_names = filtered_cells.map(cell => cell.cat);

        const new_bar_data_cell = filtered_cell_names.reduce((acc, cat) => {
                const existing_cat = acc.find(item => item.name === cat)
                if (existing_cat) {
                    existing_cat.value += 1
                } else {
                    acc.push({ name: cat, value: 1 })
                }
                return acc
            }, []).filter(item => item.value > 0)
            .sort((a, b) => b.value - a.value)

        update_bar_graph(svg_bar_cluster, new_bar_data_cell, color_dict_cluster, bar_callback_cluster, selected_cats, deck_ist)

        bar_container_cluster.scrollTo({
            top: 0,
            behavior: 'smooth'
        })


    } else {

        if (close_up) {
            set_close_up(false)
            update_layers_ist()
            update_bar_graph(svg_bar_gene, gene_counts, color_dict_gene, bar_callback_gene, selected_genes, deck_ist)
            update_bar_graph(svg_bar_cluster, cluster_counts, color_dict_cluster, bar_callback_cluster, selected_cats, deck_ist)

            bar_container_gene.scrollTo({
                top: 0,
                behavior: 'smooth'
            })

            bar_container_cluster.scrollTo({
                top: 0,
                behavior: 'smooth'
            })

        }
    }

    // turning off update for now
    // deck_ist.setProps({ layers: layers_ist })

    const layers_list = get_layers_list(layers_obj, close_up)
    deck_ist.setProps({layers: layers_list})

}
