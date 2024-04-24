// import { visibleTiles } from "../vector_tile/visibleTiles";
// import { path_layer, update_path_layer } from "../deck-gl/path_layer.js";
// import { trx_layer, update_trx_layer } from '../deck-gl/trx_layer.js';


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

//         await update_trx_layer(base_url, tiles_in_view)
//         await update_path_layer(base_url, tiles_in_view)

//         new_layers = [
//             tile_layer_2, 
//             tile_layer, 
//             path_layer, 
//             cell_layer, 
//             trx_layer]

//         update_layers(new_layers)            

//     } else {

//         new_layers = [tile_layer_2, tile_layer, cell_layer]
//         update_layers(new_layers)

//     }

//     deck.setProps({layers});
// }