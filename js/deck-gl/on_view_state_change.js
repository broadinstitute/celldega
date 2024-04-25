// import { debounce } from "../utils/debounce.js";
// import { bounce_time } from "../global_variables/bounce_time.js";
import { image_layers } from "./image_layers.js";
import { cell_layer } from "./cell_layer.js";
import { path_layer, update_path_layer } from "./path_layer.js";
import { trx_layer, update_trx_layer } from "./trx_layer.js";
import { visibleTiles } from "../vector_tile/visibleTiles.js";
import { update_layers, layers } from "./layers.js";
import { deck } from '../deck-gl/deck.js'
import { global_base_url } from "../global_variables/global_base_url.js";

export let on_view_state_change

// const bounce_time = 150

// make these customizable later
const tileSize = 1000;
const max_tiles_to_view = 15

export const calc_viewport = async ({ height, width, zoom, target }) => {

    let new_layers = []

    const zoomFactor = Math.pow(2, zoom);
    const [targetX, targetY] = target;
    const halfWidthZoomed = width / (2 * zoomFactor);
    const halfHeightZoomed = height / (2 * zoomFactor);

    const minX = targetX - halfWidthZoomed;
    const maxX = targetX + halfWidthZoomed;
    const minY = targetY - halfHeightZoomed;
    const maxY = targetY + halfHeightZoomed;

    const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tileSize);

    if (tiles_in_view.length < max_tiles_to_view) {

        await update_trx_layer(global_base_url, tiles_in_view)
        await update_path_layer(global_base_url, tiles_in_view)

        new_layers = [
            ...image_layers, 
            path_layer, 
            cell_layer, 
            trx_layer]

        update_layers(new_layers)            

    } else {

        new_layers = [...image_layers, cell_layer]
        update_layers(new_layers)

    }

    deck.setProps({layers});
}

// const debounced_calc_viewport = debounce(calc_viewport, bounce_time);

// export const set_on_view_state_change = ({viewState}) => {
//     on_view_state_change = debounced_calc_viewport(viewState)
//     return viewState    
// }