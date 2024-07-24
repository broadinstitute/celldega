import { set_trx_ini_raidus } from '../global_variables/trx_ini_raidus'
import { set_options } from '../global_variables/fetch_options'
import { set_global_base_url } from '../global_variables/global_base_url'
import { set_landscape_parameters } from '../global_variables/landscape_parameters'
import { set_dimensions } from '../global_variables/image_dimensions'
import { set_initial_view_state } from '../deck-gl/initial_view_state'
import { set_cell_layer } from "../deck-gl/cell_layer"
import { update_layers_ist } from '../deck-gl/layers_ist'
import { make_image_layers } from '../deck-gl/image_layers'
import { update_views } from '../deck-gl/views'
import { deck_ist, set_deck } from '../deck-gl/deck_ist'
import { set_background_layer } from '../deck-gl/background_layer'
import { make_ist_ui_container } from '../ui/ui_containers'
import { model, set_model } from '../global_variables/model'
import { update_trx_layer_radius } from '../deck-gl/trx_layer'
import { image_info, set_image_info, set_image_layer_colors } from '../global_variables/image_info'
import { set_image_layer_sliders } from "../ui/sliders"
import { set_meta_gene } from '../global_variables/meta_gene'
import { set_cluster_metadata } from '../global_variables/meta_cluster'
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm'
import { hexToRgb } from '../utils/hexToRgb'


export const landscape_ist = async (
    el,
    ini_model,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    base_url,
    dataset_name='',
    trx_radius=0.25,
) => {

    // move this to landscape_parameters
    const imgage_name_for_dim = 'dapi'
    const tmp_image_info = [
        {
            name: 'dapi',
            button_name: 'DAPI',
            color: hexToRgb('#0072B2')
        },
        {
            name: 'bound',
            button_name: 'BOUND',
            color: hexToRgb('#56B4E9')
        },
        {
            name: 'rna',
            button_name: 'RNA',
            color: hexToRgb('#E69F00')
        },
        {
            name: 'prot',
            button_name: 'PROT',
            color: hexToRgb('#CC79A7')
        }
    ]

    set_image_info(tmp_image_info)
    set_image_layer_sliders(image_info)
    set_image_layer_colors(image_info)


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
    await set_meta_gene(base_url)

    await set_cluster_metadata()

    // update layers
    await make_image_layers(base_url)
    await set_cell_layer(base_url)

    set_background_layer()

    update_trx_layer_radius(trx_radius)

    // update_layers_ist([background_layer, ...image_layers, cell_layer])
    update_layers_ist()

    update_views()

    set_deck(root)



    // check if ini_model is not equal to {}
    if (Object.keys(ini_model).length > 0) {
        model.on('change:update_trigger', update_ist_landscape_from_cgm)
    }

    const ui_container = make_ist_ui_container(dataset_name)

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root);

    return () => deck_ist.finalize();

}