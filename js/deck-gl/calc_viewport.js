import { visibleTiles } from '../vector_tile/visibleTiles.js'
import { global_base_url } from '../global_variables/global_base_url.js'
import { deck_ist } from './deck_ist.js'
import { update_path_layer } from './path_layer.js'
import { update_trx_layer } from './trx_layer.js'
import { layers_ist, update_layers_ist } from './layers_ist.js'
import { landscape_parameters } from '../global_variables/landscape_parameters.js'
import { set_close_up } from '../global_variables/close_up.js'

export const calc_viewport = async ({ height, width, zoom, target }) => {

    const tile_size = landscape_parameters.tile_size

    const max_tiles_to_view = 50 // 15

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

        set_close_up(true)
        update_layers_ist()

    } else {

        set_close_up(false)
        update_layers_ist()

    }

    deck_ist.setProps({
        'layers': layers_ist
    });
}