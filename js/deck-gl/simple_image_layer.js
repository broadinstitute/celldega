import { TileLayer } from 'deck.gl' 
import { create_get_tile_data } from './create_get_tile_data'
import { create_simple_render_tile_sublayers } from '../deck-gl/create_simple_render_tile_sublayer'
import { dimensions } from '../global_variables/image_dimensions'
import { global_base_url } from '../global_variables/global_base_url'
import { landscape_parameters } from '../global_variables/landscape_parameters'
import { options } from '../global_variables/fetch_options'

export let simple_image_layer

export const make_simple_image_layer = async (info) => {

    simple_image_layer = new TileLayer({
        id: 'global-simple-image-layer',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(global_base_url, info.name, landscape_parameters.max_pyramid_zoom, options),
        renderSubLayers: create_simple_render_tile_sublayers(dimensions),
        visible: true
    });     

}

export const simple_image_layer_visibility = (visible) => {

    simple_image_layer = simple_image_layer.clone({
        visible: visible,
        // opacity: 0.1
    });

}
