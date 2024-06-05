import { TileLayer } from 'deck.gl' 
import { create_get_tile_data } from './create_get_tile_data'
import { create_simple_render_tile_sublayers } from '../deck-gl/create_simple_render_tile_sublayer'
import { get_image_dimensions } from "../image_tile/get_image_dimensions.js"; 
import { global_base_url } from '../global_variables/global_base_url'
import { landscape_parameters } from '../global_variables/landscape_parameters'
import { options } from '../global_variables/fetch_options'

export let simple_image_layer

export const make_simple_image_layer = async (info) => {


    const dimensions = await get_image_dimensions(global_base_url, 'cells', options)


    console.log('checking the global variables')
    console.log(options)
    console.log(landscape_parameters)
    console.log(global_base_url)
    console.log('dimensions', dimensions)    

    console.log('update simple_image_layer')

    simple_image_layer = new TileLayer({
        id: 'global-simple-image-layer',// info.name,
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(global_base_url, info.name, landscape_parameters.max_pyramid_zoom, options),
        renderSubLayers: create_simple_render_tile_sublayers(dimensions, info.color)
    });     

}