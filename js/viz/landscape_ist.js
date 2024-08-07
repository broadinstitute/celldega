import { set_trx_ini_raidus } from '../global_variables/trx_ini_raidus'
import { set_options } from '../global_variables/fetch_options'
import { set_global_base_url } from '../global_variables/global_base_url'
import { landscape_parameters, set_landscape_parameters } from '../global_variables/landscape_parameters'
import { set_dimensions } from '../global_variables/image_dimensions'
import { set_initial_view_state } from '../deck-gl/initial_view_state'
import { ini_cell_layer, set_cell_layer_onclick } from "../deck-gl/cell_layer"
import { get_layers_list } from '../deck-gl/layers_ist'
import { image_layers, make_image_layers } from '../deck-gl/image_layers'
import { update_views } from '../deck-gl/views'
import { ini_deck, set_deck_on_view_state_change } from '../deck-gl/deck_ist'
import { background_layer, set_background_layer } from '../deck-gl/background_layer'
import { ini_path_layer, set_path_layer_onclick } from '../deck-gl/path_layer'
import { make_ist_ui_container } from '../ui/ui_containers'
import { model, set_model } from '../global_variables/model'
import { ini_trx_layer, set_trx_layer, set_trx_layer_onclick, update_trx_layer_radius } from '../deck-gl/trx_layer'
import { image_info, set_image_info, set_image_layer_colors } from '../global_variables/image_info'
import { set_image_format } from '../global_variables/image_info'
import { set_image_layer_sliders } from "../ui/sliders"
import { set_meta_gene } from '../global_variables/meta_gene'
import { set_cluster_metadata } from '../global_variables/meta_cluster'
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm'
import { update_cell_clusters } from '../widget_interactions/update_cell_clusters'
import { close_up } from '../global_variables/close_up'

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

    set_options(token)

    // move this to landscape_parameters
    const imgage_name_for_dim = 'dapi'

    await set_landscape_parameters(base_url)

    const tmp_image_info = landscape_parameters.image_info

    set_image_format(landscape_parameters.image_format)
    set_image_info(tmp_image_info)
    set_image_layer_sliders(image_info)
    set_image_layer_colors(image_info)

    // Create and append the visualization.
    set_trx_ini_raidus(trx_radius)
    let root = document.createElement("div")
    root.style.height = "800px"

    set_model(ini_model)

    set_global_base_url(base_url)

    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)
    await set_dimensions(base_url, imgage_name_for_dim)

    await set_meta_gene(base_url)

    await set_cluster_metadata()

    // update layers
    await make_image_layers(base_url)

    set_background_layer()

    update_views()

    let deck_ist = await ini_deck(root)

    let cell_layer = await ini_cell_layer(base_url)
    let path_layer = await ini_path_layer()
    let trx_layer = ini_trx_layer()

    // make layers object
    let layers_obj = {
        'background_layer': background_layer,
        'image_layers': image_layers,
        'path_layer': path_layer,
        'cell_layer': cell_layer,
        'trx_layer': trx_layer
    }

    set_cell_layer_onclick(deck_ist, layers_obj)
    set_path_layer_onclick(deck_ist, layers_obj)
    set_trx_layer_onclick(deck_ist, layers_obj)

    await set_trx_layer(deck_ist)
    update_trx_layer_radius(trx_radius)

    const layers_list = get_layers_list(layers_obj, close_up)
    deck_ist.setProps({layers: layers_list})

    set_deck_on_view_state_change(deck_ist, layers_obj)

    // check if ini_model is not equal to {}
    if (Object.keys(ini_model).length > 0) {
        model.on('change:update_trigger', () => update_ist_landscape_from_cgm(deck_ist))
        model.on('change:cell_clusters', () => update_cell_clusters(deck_ist))
    }

    const ui_container = make_ist_ui_container(dataset_name, deck_ist)

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root)

    const landscape = {
        update_view_state: () => {
            console.log('updating view state!!!')
        },
        update_layers: () => {
            console.log('update_layers')
        },
        finalize: () => {
            deck_ist.finalize();
        }
    };

    return landscape;

}

