import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { global_base_url } from '../global_variables/global_base_url.js'
import { deck_ist } from './deck_ist.js'
import { update_path_layer } from './path_layer.js'
import { update_trx_layer } from './trx_layer.js'
import { layers_ist, update_layers_ist } from './layers_ist.js'
import { landscape_parameters } from '../global_variables/landscape_parameters.js'
import { close_up, set_close_up } from '../global_variables/close_up.js'
import { trx_names_array } from '../global_variables/trx_names_array.js'
import { svg_bar_gene, update_bar_cluster } from '../ui/bar_plot.js'
import { gene_color_dict } from '../global_variables/gene_color_dict.js'
import { trx_data } from '../vector_tile/transcripts/trx_data.js'
import { gene_counts } from '../global_variables/meta_gene.js'
import { bar_gene_callback } from '../ui/bar_plot.js'

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

    // const viewport = deck_ist.viewports[0]

    // console.log('deck_ist.viewports', deck_ist.viewports)
    // console.log(deck_ist.viewManager.getViewports())
    // console.log(deck_ist.viewManager.getViewports())
    // console.log(deck_ist.viewManager.getViewports()[0])

    // console.log(targetX, targetY, halfWidthZoomed, halfHeightZoomed)

    // Get the current viewport from Deck.gl
    const viewports = deck_ist.viewManager.getViewports()
    if (!viewports || viewports.length === 0) {
        // console.error('No viewports available')
        return
    }
    const viewport = viewports[0]

    // Get the bounding box in world coordinates (note that Y is swapped because of screen coordinate convention)
    const [tmp_minX, tmp_maxY] = viewport.unproject([0, viewport.height])
    const [tmp_maxX, tmp_minY] = viewport.unproject([viewport.width, 0])


    // console.log('compare!!!')
    // console.log(minX, maxX, minY, maxY)
    // console.log(tmp_minX, tmp_maxX, tmp_minY, tmp_maxY)


    const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tile_size)

    if (tiles_in_view.length < max_tiles_to_view) {
        await update_trx_layer(global_base_url, tiles_in_view)
        await update_path_layer(global_base_url, tiles_in_view)

        set_close_up(true)
        update_layers_ist()

        // console.log('close up')

        if (trx_data && trx_data.attributes?.getPosition?.value) {
            const positionsArray = Float64Array.from(trx_data.attributes.getPosition.value)
            const positions = []
            for (let i = 0; i < positionsArray.length; i += 2) {
                positions.push({ x: positionsArray[i], y: positionsArray[i + 1] })
            }

            // Filter transcripts based on viewport
            const filtered_transcripts = positions.filter(pos =>
                pos.x >= minX && pos.x <= maxX && pos.y >= minY && pos.y <= maxY
            )

            // Calculate gene counts for filtered transcripts
            const filtered_gene_names = filtered_transcripts.map((_, index) => trx_names_array[index])


            // const filtered_gene_names = trx_names_array // filtered_transcripts.map((_, index) => trx_names_array[index])

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

            // console.log(new_bar_data)

            update_bar_cluster(svg_bar_gene, new_bar_data, gene_color_dict, bar_gene_callback)
        } else {
            // console.error("trx_data.attributes.getPosition.value is undefined or not iterable")
        }
    } else {
        set_close_up(false)
        update_layers_ist()

        // console.log('not close up')
        update_bar_cluster(svg_bar_gene, gene_counts, gene_color_dict, bar_gene_callback)
    }

    deck_ist.setProps({ layers: layers_ist })
}
