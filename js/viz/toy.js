import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_views } from '../deck-gl/views.js';
import { set_initial_view_state } from "../deck-gl/initial_view_state.js";

import { deck, set_deck } from '../deck-gl/toy_deck.js'
import { update_layers } from "../deck-gl/toy_layers.js";
import { square_scatter_layer, ini_square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";  

import { update_tile_scatter_data } from "../global_variables/tile_scatter_data.js";
import { update_tile_cat } from "../global_variables/tile_cat.js"
import { update_tile_cats_array } from "../global_variables/tile_cats_array.js";
import { update_tile_names_array } from "../global_variables/tile_names_array.js";
import { update_tile_color_dict } from "../global_variables/tile_color_dict.js";
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"; 

import { set_meta_gene } from "../global_variables/meta_gene.js";

import { input } from "../ui/input.js";
import { update_selected_cats } from "../global_variables/selected_cats.js";

import { get_image_dimensions } from "../image_tile/get_image_dimensions.js"; 

import { set_landscape_parameters, landscape_parameters } from "../global_variables/landscape_parameters.js";
import { TileLayer } from 'deck.gl' 

import { create_get_tile_data } from '../deck-gl/create_get_tile_data.js'
import { create_simple_render_tile_sublayers } from '../deck-gl/create_simple_render_tile_sublayer'


export const toy = async ( model, root, base_url ) => {

    set_options('')

    await set_landscape_parameters(base_url)

    const dimensions = await get_image_dimensions(base_url, 'cells', options)

    console.log('dimensions')
    console.log(dimensions)

    // move this to landscape_parameters
    // const imgage_name_for_dim = 'dapi'
    const info = { 
        name: 'cells', 
        color: [0, 0, 255]
    }

    const max_pyramid_zoom = landscape_parameters.max_pyramid_zoom

    console.log('max_pyramid_zoom', max_pyramid_zoom)

    const image_layer = new TileLayer({
        id: info.name,
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20,
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(base_url, info.name, max_pyramid_zoom, options),
        renderSubLayers: create_simple_render_tile_sublayers(dimensions, info.color)
    });     

    const tile_url = base_url + 'tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)

    update_tile_scatter_data(get_scatter_data(tile_arrow_table))
    update_tile_cats_array(tile_arrow_table.getChild("cluster").toArray())
    update_tile_names_array(tile_arrow_table.getChild("name").toArray())

    await set_meta_gene(base_url)
    await update_tile_color_dict(base_url)
    ini_square_scatter_layer(base_url)
    const new_layers = [image_layer, square_scatter_layer]
    await update_layers(new_layers)

    const ini_x = 10000
    const ini_y = 14000
    const ini_z = 0
    const ini_zoom = -5

    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)    
    update_views()

    set_deck(root)

    model.on('change:update_trigger', async () => {

        const click_info = model.get('update_trigger');

        let selected_gene
        if (click_info.click_type === 'row-label') {

            selected_gene = click_info.click_value 
            update_tile_cat(selected_gene)
            await update_tile_exp_array(base_url, selected_gene)

        } else if (click_info.click_type === 'col-label') {

            selected_gene = 'cluster'
            update_tile_cat(selected_gene)
            update_selected_cats([click_info.click_value])
        
        } else if (click_info.click_type === 'col-dendro') {
            
            selected_gene = 'cluster'
            update_tile_cat(selected_gene)
            update_selected_cats(click_info.click_value)        
        
        } else {
            selected_gene = 'cluster'
            update_tile_cat(selected_gene)
        }

        input.value = selected_gene
        
        update_square_scatter_layer()
        deck.setProps({layers: [image_layer, square_scatter_layer]})

    });        

    return () => deck.finalize();  

}