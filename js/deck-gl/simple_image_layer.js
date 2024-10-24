import { TileLayer } from 'deck.gl'
import { create_get_tile_data } from './create_get_tile_data'
import { create_simple_render_tile_sublayers } from '../deck-gl/create_simple_render_tile_sublayer'
import { options } from '../global_variables/fetch_options'

export const make_simple_image_layer = async (viz_state, info) => {

    let global_base_url = viz_state.global_base_url
    let dimensions = viz_state.dimensions
    let landscape_parameters = viz_state.img.landscape_parameters
    let image_format = viz_state.img.landscape_parameters.image_format

    let simple_image_layer = new TileLayer({
        id: 'global-simple-image-layer',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(global_base_url, info.name, image_format, landscape_parameters.max_pyramid_zoom, options),
        renderSubLayers: create_simple_render_tile_sublayers(dimensions),
        visible: true
    })

    return simple_image_layer

}

// export const simple_image_layer_visibility = (visible) => {

//     simple_image_layer = simple_image_layer.clone({
//         visible: visible,
//         // opacity: 0.1
//     });

// }
