import { set_trx_ini_raidus } from '../global_variables/trx_ini_raidus.js';
import { set_options } from '../global_variables/fetch_options.js';
import { set_global_base_url } from '../global_variables/global_base_url.js';
import { set_landscape_parameters } from '../global_variables/landscape_parameters.js';
import { set_dimensions } from '../global_variables/image_dimensions.js';
import { set_initial_view_state } from '../deck-gl/initial_view_state.js';
import { cell_layer, update_cell_layer } from "../deck-gl/cell_layer.js";
import { update_layers } from '../deck-gl/layers.js';
import { image_layers, make_image_layers } from '../deck-gl/image_layers.js';
import { update_views } from '../deck-gl/views.js';
import { deck_ist, set_deck } from '../deck-gl/deck_ist.js';
import { background_layer, update_background_layer } from '../deck-gl/background_layer.js';
import { make_ist_ui_container } from '../ui/ui_containers.js';
import { set_model } from '../global_variables/model.js';
import { update_trx_layer_radius } from '../deck-gl/trx_layer.js';
import { image_info, image_layer_colors, set_image_info, set_image_layer_colors } from '../global_variables/image_info.js';
import { image_layer_sliders, set_image_layer_sliders } from "../ui/sliders"
import { image } from 'd3';

export const landscape_ist = async (
    el,
    ini_model,
    token, 
    ini_x, 
    ini_y, 
    ini_z, 
    ini_zoom, 
    base_url, 
    trx_radius=0.25
) => {

    console.log('landscape_ist')

    // move this to landscape_parameters
    const imgage_name_for_dim = 'dapi'
    const tmp_image_info = [
        { 
            name: 'dapi', 
            button_name: 'DAPI',
            color: [0, 0, 255]
        },
        {   
            name: 'cellbound', 
            button_name: 'BOUND',
            color: [255, 0, 0]
        }
    ]

    set_image_info(tmp_image_info)
    set_image_layer_sliders(image_info)
    set_image_layer_colors(image_info)

    console.log('image_layer_colors')
    console.log('-------------------------')
    console.log(image_layer_colors)

    console.log('landscape_ist: image_layer_sliders', image_layer_sliders)

    // Create and append the visualization.
    set_trx_ini_raidus(trx_radius)
    let root = document.createElement("div");
    root.style.height = "800px";

    set_model(ini_model)

    set_global_base_url(base_url)
    
    set_options(token)
    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)
    await set_dimensions(base_url, imgage_name_for_dim )
    await set_landscape_parameters(base_url)

    // update layers
    await make_image_layers(base_url)
    await update_cell_layer(base_url)

    update_background_layer()

    update_trx_layer_radius(trx_radius)

    update_layers([background_layer, ...image_layers, cell_layer])
    update_views()

    set_deck(root)

    const ui_container = make_ist_ui_container()

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root);     

    return () => deck_ist.finalize();        

}