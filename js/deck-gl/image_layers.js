import { TileLayer } from 'deck.gl'
import { create_get_tile_data } from './create_get_tile_data'
import { create_render_tile_sublayers } from './create_render_tile_sublayer'
import { options } from '../global_variables/fetch_options'
import { landscape_parameters } from '../global_variables/landscape_parameters'
import { image_layer_colors } from '../global_variables/image_info'

const make_image_layer = (viz_state, info) => {

    const max_pyramid_zoom = landscape_parameters.max_pyramid_zoom

    const opacity = 5

    const image_layer = new TileLayer({
        id: info.button_name,
        tileSize: viz_state.dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, viz_state.dimensions.width, viz_state.dimensions.height],
        getTileData: create_get_tile_data(viz_state.global_base_url, info.name, viz_state.img.image_format, max_pyramid_zoom, options),
        renderSubLayers: create_render_tile_sublayers(viz_state, info.color, opacity)
    });
    return image_layer
}

export const make_image_layers = async (viz_state) => {
    let image_layers = viz_state.img.image_info.map( (info) => make_image_layer(viz_state, info) );
    return image_layers
}

export const toggle_visibility_image_layers = (layers_obj, visible) => {
    layers_obj.image_layers = layers_obj.image_layers.map(layer =>
        layer.clone({
            visible: visible
        })
    )
}

export const toggle_visibility_single_image_layer = (layers_obj, name, visible) => {

    layers_obj.image_layers = layers_obj.image_layers.map(layer =>
        layer.id.startsWith(name) ?
        layer.clone({ visible: visible }) :
        layer
    )

}

export const update_opacity_single_image_layer = (layers_obj, name, opacity) => {

    let color = image_layer_colors[name]

    layers_obj.image_layers = layers_obj.image_layers.map(layer =>
        layer.id.startsWith(name) ?
        layer.clone({
            renderSubLayers: create_render_tile_sublayers(color, opacity),
            id: name + '-' + opacity
        }) :
        layer
    )

}