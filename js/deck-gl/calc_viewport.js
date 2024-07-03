import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { global_base_url } from '../global_variables/global_base_url.js'
import { deck_ist } from './deck_ist.js'
import { image_layers } from './image_layers.js'
import { cell_layer } from './cell_layer.js'
import { path_layer, update_path_layer } from './path_layer.js'
import { trx_layer, update_trx_layer } from './trx_layer.js'
import { layers, update_layers } from './layers.js'
import { landscape_parameters } from '../global_variables/landscape_parameters.js'
import { background_layer } from './background_layer.js'

export const calc_viewport = async ({ height, width, zoom, target }) => {

    const tile_size = landscape_parameters.tile_size

    const max_tiles_to_view = 50 // 15

    let new_layers = []

    const zoomFactor = Math.pow(2, zoom);
    const [targetX, targetY] = target;
    const halfWidthZoomed = width / (2 * zoomFactor);
    const halfHeightZoomed = height / (2 * zoomFactor);

    const minX = targetX - halfWidthZoomed;
    const maxX = targetX + halfWidthZoomed;
    const minY = targetY - halfHeightZoomed;
    const maxY = targetY + halfHeightZoomed;

    const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tile_size);

    if (tiles_in_view.length < max_tiles_to_view) {

        await update_trx_layer(global_base_url, tiles_in_view)
        await update_path_layer(global_base_url, tiles_in_view)

        new_layers = [
            background_layer,
            ...image_layers, 
            path_layer, 
            cell_layer, 
            trx_layer
        ]

        update_layers(new_layers)            

    } else {

        new_layers = [
            background_layer,
            ...image_layers, 
            cell_layer
        ]

        update_layers(new_layers)

    }

    deck_ist.setProps({layers});
}