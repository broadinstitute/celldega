// import { visibleTiles } from "../vector_tile/visibleTiles.js";
// import { image_layers, update_image_layers } from '../deck-gl/image_layers.js';
// import { cell_layer, update_cell_layer } from "../deck-gl/cell_layer.js";
// import { path_layer, update_path_layer } from "../deck-gl/path_layer.js";
// import { trx_layer, update_trx_layer } from '../deck-gl/trx_layer.js';
// import { global_base_url } from "../global_variables/global_base_url.js";
// import { layers, update_layers } from '../deck-gl/layers.js';
// import { deck } from '../deck-gl/deck.js'


// const tileSize = 1000;
// const max_tiles_to_view = 15

// export const calc_viewport = async ({ height, width, zoom, target }) => {

//     let new_layers = []

//     const zoomFactor = Math.pow(2, zoom);
//     const [targetX, targetY] = target;
//     const halfWidthZoomed = width / (2 * zoomFactor);
//     const halfHeightZoomed = height / (2 * zoomFactor);

//     const minX = targetX - halfWidthZoomed;
//     const maxX = targetX + halfWidthZoomed;
//     const minY = targetY - halfHeightZoomed;
//     const maxY = targetY + halfHeightZoomed;

//     const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tileSize);

//     if (tiles_in_view.length < max_tiles_to_view) {

//         await update_trx_layer(global_base_url, tiles_in_view)
//         await update_path_layer(global_base_url, tiles_in_view)

//         new_layers = [
//             ...image_layers, 
//             path_layer, 
//             cell_layer, 
//             trx_layer]

//         update_layers(new_layers)            

//     } else {

//         new_layers = [...image_layers, cell_layer]
//         update_layers(new_layers)

//     }

//     deck.setProps({layers});
// }