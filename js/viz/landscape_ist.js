import { set_trx_ini_raidus } from '../global_variables/trx_ini_raidus'
import { set_options } from '../global_variables/fetch_options'
import { set_global_base_url } from '../global_variables/global_base_url'
import { landscape_parameters, set_landscape_parameters } from '../global_variables/landscape_parameters'
import { set_dimensions } from '../global_variables/image_dimensions'
import { ini_cell_layer, set_cell_layer_onclick } from "../deck-gl/cell_layer"
import { get_layers_list } from '../deck-gl/layers_ist'
import { make_image_layers } from '../deck-gl/image_layers'
import { set_views, ini_viz_state } from '../deck-gl/views'
import { ini_deck, set_deck_on_view_state_change, set_initial_view_state, set_get_tooltip, set_views_prop } from '../deck-gl/deck_ist'
import { ini_background_layer } from '../deck-gl/background_layer'
import { ini_path_layer, set_path_layer_onclick } from '../deck-gl/path_layer'
import { make_ist_ui_container } from '../ui/ui_containers'
import { model, set_model } from '../global_variables/model'
import { ini_trx_layer, set_trx_layer_onclick, update_trx_layer_radius } from '../deck-gl/trx_layer'
import { image_info, set_image_info, set_image_layer_colors } from '../global_variables/image_info'
import { set_image_format } from '../global_variables/image_info'
import { set_image_layer_sliders } from "../ui/sliders"
import { set_meta_gene } from '../global_variables/meta_gene'
import { set_cluster_metadata } from '../global_variables/meta_cluster'
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm'
import { update_cell_clusters } from '../widget_interactions/update_cell_clusters'
import { ini_cache } from '../global_variables/cache'

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

    console.log('hi from the flight!')
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

    await set_dimensions(base_url, imgage_name_for_dim)

    await set_meta_gene(base_url)

    await set_cluster_metadata()

    let viz_state = ini_viz_state()

    viz_state.views = set_views()

    let deck_ist = await ini_deck(root)
    set_initial_view_state(deck_ist, ini_x, ini_y, ini_z, ini_zoom)
    set_views_prop(deck_ist, viz_state.views)

    viz_state.cats = {}
    viz_state.cats.cat
    viz_state.cats.reset_cat = false
    viz_state.cats.selected_cats = []
    viz_state.cats.cell_cats = []
    viz_state.cats.dict_cell_cats = {}
    viz_state.cats.cell_exp_array = []

    // initialize cell and trx caches
    viz_state.cache = {}
    viz_state.cache.cell = await ini_cache()
    // we will try to reuse cell functions to make trx cache
    viz_state.cache.trx  = await ini_cache()

    viz_state.combo_data = {}

    viz_state.tooltip_cat_cell = ''

    set_get_tooltip(deck_ist, viz_state)

    let background_layer = ini_background_layer()
    let image_layers = await make_image_layers(base_url)
    let cell_layer = await ini_cell_layer(base_url, viz_state)
    let path_layer = await ini_path_layer(viz_state)
    let trx_layer = ini_trx_layer()

    // make layers object
    let layers_obj = {
        'background_layer': background_layer,
        'image_layers': image_layers,
        'cell_layer': cell_layer,
        'path_layer': path_layer,
        'trx_layer': trx_layer
    }

    set_cell_layer_onclick(deck_ist, layers_obj, viz_state)
    set_path_layer_onclick(deck_ist, layers_obj, viz_state)
    set_trx_layer_onclick(deck_ist, layers_obj, viz_state)

    update_trx_layer_radius(layers_obj, trx_radius)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})



    set_deck_on_view_state_change(deck_ist, layers_obj, viz_state)

    // check if ini_model is not equal to {}
    if (Object.keys(ini_model).length > 0) {
        model.on('change:update_trigger', () => update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state))
        model.on('change:cell_clusters', () => update_cell_clusters(deck_ist, layers_obj, viz_state))
    }

    const ui_container = make_ist_ui_container(dataset_name, deck_ist, layers_obj, viz_state)

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

