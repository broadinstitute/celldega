import { set_options } from '../global_variables/fetch_options.js';
import { set_global_base_url } from '../global_variables/global_base_url.js';
import { set_landscape_parameters } from '../global_variables/landscape_parameters.js';
import { set_dimensions } from '../global_variables/image_dimensions.js';
import { set_initial_view_state } from '../deck-gl/initial_view_state.js';
import { cell_layer, update_cell_layer } from "../deck-gl/cell_layer.js";
import { update_layers } from '../deck-gl/layers.js';
import { image_layers, update_image_layers } from '../deck-gl/image_layers.js';
import { update_views } from '../deck-gl/views.js';
import { deck, set_deck } from '../deck-gl/deck.js';

export const landscape = async (
    token, 
    ini_x, 
    ini_y, 
    ini_z, 
    ini_zoom, 
    base_url, 
    root
) => {

    // move this to landscape_parameters
    const imgage_name_for_dim = 'dapi'
    const image_info = [
        { 
            name: 'dapi', 
            color: [0, 0, 255]
        },
        {   
            name: 'cellbound', 
            color: [255, 0, 0]
        }
    ]    

    // set global variables
    set_global_base_url(base_url)
    
    set_options(token)
    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)
    await set_dimensions(base_url, imgage_name_for_dim )
    await set_landscape_parameters(base_url)

    // update layers
    await update_image_layers(base_url, image_info)
    await update_cell_layer(base_url)
    update_layers([...image_layers, cell_layer])
    update_views()        

    set_deck(root)

    return () => deck.finalize();        

}