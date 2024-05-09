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


export const toy = async ( model, root, base_url ) => {

    set_options('')

    const tile_url = base_url + 'tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)

    update_tile_scatter_data(get_scatter_data(tile_arrow_table))
    update_tile_cats_array(tile_arrow_table.getChild("cluster").toArray())
    update_tile_names_array(tile_arrow_table.getChild("name").toArray())

    await set_meta_gene(base_url)
    await update_tile_color_dict(base_url)
    ini_square_scatter_layer(base_url)
    const new_layers = [square_scatter_layer]
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
        deck.setProps({layers: [square_scatter_layer]})

    });        

    return () => deck.finalize();  

}