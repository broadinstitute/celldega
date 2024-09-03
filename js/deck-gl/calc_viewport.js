import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { update_path_layer_data } from './path_layer.js'
import { update_trx_layer_data } from './trx_layer.js'
import { get_layers_list } from './layers_ist.js'
import { svg_bar_gene, update_bar_graph } from '../ui/bar_plot.js'
import { gene_counts } from '../global_variables/meta_gene.js'
import { bar_callback_gene, svg_bar_cluster, bar_callback_cluster } from '../ui/bar_plot.js'
import { color_dict_cluster, cluster_counts } from '../global_variables/meta_cluster.js'
import { selected_genes } from '../global_variables/selected_genes.js'

export const calc_viewport = async ({ height, width, zoom, target }, deck_ist, layers_obj, viz_state) => {

    const tile_size = viz_state.img.landscape_parameters.tile_size
    const max_tiles_to_view = 50
    const zoomFactor = Math.pow(2, zoom)
    const [targetX, targetY] = target
    const halfWidthZoomed = width / (2 * zoomFactor)
    const halfHeightZoomed = height / (2 * zoomFactor)

    viz_state.bounds = {}
    viz_state.bounds.min_x = targetX - halfWidthZoomed
    viz_state.bounds.max_x = targetX + halfWidthZoomed
    viz_state.bounds.min_y = targetY - halfHeightZoomed
    viz_state.bounds.max_y = targetY + halfHeightZoomed

    // Get the current viewport from Deck.gl
    const viewports = deck_ist.viewManager.getViewports()
    if (!viewports || viewports.length === 0) {
        console.error('No viewports available')
        return
    }

    const tiles_in_view = visibleTiles(
        viz_state.bounds.min_x,
        viz_state.bounds.max_x,
        viz_state.bounds.min_y,
        viz_state.bounds.max_y,
        tile_size
    )

    if (tiles_in_view.length < max_tiles_to_view) {

        await update_trx_layer_data(viz_state.global_base_url, tiles_in_view, layers_obj, viz_state)

        await update_path_layer_data(viz_state.global_base_url, tiles_in_view, layers_obj, viz_state)

        viz_state.close_up = true

        // gene bar graph update
        const filtered_transcripts = viz_state.combo_data.trx.filter(pos =>
            pos.x >= viz_state.bounds.min_x &&
            pos.x <= viz_state.bounds.max_x &&
            pos.y >= viz_state.bounds.min_y &&
            pos.y <= viz_state.bounds.max_y
        )

        const filtered_gene_names = filtered_transcripts.map(transcript => transcript.name)

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

        update_bar_graph(svg_bar_gene, new_bar_data, viz_state.genes.color_dict_gene, bar_callback_gene, selected_genes, deck_ist, layers_obj, viz_state)

        viz_state.containers.bar_gene.scrollTo({
            top: 0,
            behavior: 'smooth'
        })

        // cell bar graph update
        const filtered_cells = viz_state.combo_data.cell.filter(pos =>
            pos.x >= viz_state.bounds.min_x &&
            pos.x <= viz_state.bounds.max_x &&
            pos.y >= viz_state.bounds.min_y &&
            pos.y <= viz_state.bounds.max_y
        )

        const filtered_cell_names = filtered_cells.map(cell => cell.cat)

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

        update_bar_graph(svg_bar_cluster, new_bar_data_cell, color_dict_cluster, bar_callback_cluster, viz_state.cats.selected_cats, deck_ist, layers_obj, viz_state)

        viz_state.containers.bar_cluster.scrollTo({
            top: 0,
            behavior: 'smooth'
        })


    } else {

        if (viz_state.close_up) {

            // set_close_up(false)
            viz_state.close_up = false

            update_bar_graph(svg_bar_gene, gene_counts, viz_state.genes.color_dict_gene, bar_callback_gene, selected_genes, deck_ist, layers_obj, viz_state)
            update_bar_graph(svg_bar_cluster, cluster_counts, color_dict_cluster, bar_callback_cluster, viz_state.cats.selected_cats, deck_ist, layers_obj, viz_state)

            viz_state.containers.bar_gene.scrollTo({
                top: 0,
                behavior: 'smooth'
            })

            viz_state.containers.bar_cluster.scrollTo({
                top: 0,
                behavior: 'smooth'
            })

        }
    }

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}
