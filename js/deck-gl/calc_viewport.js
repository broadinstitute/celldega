import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { global_base_url } from '../global_variables/global_base_url.js'
import { deck_ist } from './deck_ist.js'
import { update_path_layer } from './path_layer.js'
import { update_trx_layer } from './trx_layer.js'
import { layers_ist, update_layers_ist } from './layers_ist.js'
import { landscape_parameters } from '../global_variables/landscape_parameters.js'
import { set_close_up } from '../global_variables/close_up.js'
import { trx_names_array } from '../global_variables/trx_names_array.js'
import { svg_bar_gene, update_bar_cluster } from '../ui/bar_plot.js'
import { gene_color_dict } from '../global_variables/gene_color_dict.js'

export let minX
export let maxX
export let minY
export let maxY

export const calc_viewport = async ({ height, width, zoom, target }) => {

    const tile_size = landscape_parameters.tile_size

    const max_tiles_to_view = 50 // 15

    const zoomFactor = Math.pow(2, zoom);
    const [targetX, targetY] = target;
    const halfWidthZoomed = width / (2 * zoomFactor);
    const halfHeightZoomed = height / (2 * zoomFactor);

    minX = targetX - halfWidthZoomed;
    maxX = targetX + halfWidthZoomed;
    minY = targetY - halfHeightZoomed;
    maxY = targetY + halfHeightZoomed;

    const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tile_size);

    if (tiles_in_view.length < max_tiles_to_view) {

        await update_trx_layer(global_base_url, tiles_in_view)
        await update_path_layer(global_base_url, tiles_in_view)

        set_close_up(true)
        update_layers_ist()

        // console.log(trx_names_array)

        // const geneCounts = trx_names_array.reduce((acc, gene) => {
        //     acc[gene] = (acc[gene] || 0) + 1
        //     return acc
        //   }, {}

        // // geneCounts.sort((a, b) => b.value - a.value)

        // console.log(geneCounts)

        // const new_bar_data = [
        //     {name: 'MMP2', value: 40},
        //     {name: 'SUMO1', value: 50},
        //     {name: 'IL3', value: 60}
        // ]

        // new_bar_data.sort((a, b) => b.value - a.value)


        const new_bar_data = trx_names_array.reduce((acc, gene) => {
            // Check if the gene is already in the accumulator
            const existingGene = acc.find(item => item.name === gene)
            if (existingGene) {
                // If the gene is found, increment its value
                existingGene.value += 1
            } else {
                // If the gene is not found, add a new object with name and value
                acc.push({ name: gene, value: 1 })
            }
            return acc
        }, []).sort((a, b) => b.value - a.value)

        update_bar_cluster(svg_bar_gene, new_bar_data, gene_color_dict)

        // // Filter transcripts based on viewport
        // const filtered_transcripts = trx_names_array.filter((_, index) => {
        //     const [x, y] = trx_coords_array[index]
        //     return x >= minX && x <= maxX && y >= minY && y <= maxY
        // })

        // // Calculate gene counts
        // const new_bar_data = filtered_transcripts.reduce((acc, gene) => {
        //     const existing_gene = acc.find(item => item.name === gene)
        //     if (existing_gene) {
        //         existing_gene.value += 1
        //     } else {
        //         acc.push({ name: gene, value: 1 })
        //     }
        //     return acc
        // }, []).sort((a, b) => b.value - a.value)

        // // Update bar plot
        // update_bar_cluster(svg_bar_gene, new_bar_data, gene_color_dict)



    } else {

        set_close_up(false)
        update_layers_ist()

    }

    deck_ist.setProps({
        'layers': layers_ist
    });
}