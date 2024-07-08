import { TileLayer } from 'deck.gl' 
import { create_get_tile_data } from './create_get_tile_data'
import { create_render_tile_sublayers } from './create_render_tile_sublayer'
import { dimensions } from '../global_variables/image_dimensions'
import { options } from '../global_variables/fetch_options'
import { landscape_parameters } from '../global_variables/landscape_parameters' 
import { global_base_url } from '../global_variables/global_base_url'
import { image_info } from '../global_variables/image_info'

export let image_layers = []

const make_image_layer = (info) => {

    const max_pyramid_zoom = landscape_parameters.max_pyramid_zoom

    const opacity = 6

    const image_layer = new TileLayer({
        id: info.button_name,
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(global_base_url, info.name, max_pyramid_zoom, options),
        renderSubLayers: create_render_tile_sublayers(info.color, opacity)
    }); 
    return image_layer
}

export const make_image_layers = async (global_base_url) => {
    image_layers = image_info.map(make_image_layer);
}

export const toggle_visibility_image_layers = (visible) => {
    image_layers = image_layers.map(layer => 
        layer.clone({
            visible: visible
        })
    )
}

export const toggle_visibility_single_image_layer = (name, visible) => {

    image_layers = image_layers.map(layer => 
        layer.id === name ? 
        layer.clone({ visible: visible }) : 
        layer
    );    

}