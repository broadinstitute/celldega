import { TileLayer } from 'deck.gl' 
import { create_get_tile_data } from './create_get_tile_data'
import { create_render_tile_sublayers } from './create_render_tile_sublayer'
import { dimensions } from '../global_variables/image_dimensions'
import { options } from '../global_variables/fetch_options'
import { landscape_parameters } from '../global_variables/landscape_parameters' 
import { global_base_url } from '../global_variables/global_base_url'

export let image_layers = []

const make_image_layer = (info) => {

    const max_pyramid_zoom = landscape_parameters.max_pyramid_zoom

    const image_layer = new TileLayer({
        id: info.name,
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(global_base_url, info.name, max_pyramid_zoom, options),
        renderSubLayers: create_render_tile_sublayers(dimensions, info.color)
    }); 
    return image_layer
}

export const update_image_layers = (global_base_url, image_info) => {
    console.log('update image_layers', global_base_url) 
    image_layers = image_info.map(make_image_layer);
}
