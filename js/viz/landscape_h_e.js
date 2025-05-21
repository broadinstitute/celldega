
import { set_landscape_parameters } from "../global_variables/landscape_parameters.js"
import { options, set_options } from '../global_variables/fetch_options.js'
import { set_global_base_url } from "../global_variables/global_base_url.js"
import { set_dimensions } from '../global_variables/image_dimensions.js'
import { make_simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { set_views } from '../deck-gl/views.js'
import { ini_deck_sst } from '../deck-gl/deck_sst.js'
import { AwsClient } from 'https://esm.sh/aws4fetch@1'

export const landscape_h_e = async (
    ini_model,
    el,
    base_url,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    dataset_name='',
    width = 0,
    height = 800,
    creds={}
) => {

    console.log('landscape_h_e')

    if (width === 0){
        width = '100%'
    }

    // Create and append the visualization container
    let root = document.createElement("div")
    root.style.height = `${height}px`

    console.log('height', height)
    console.log(root.style.height)

    let viz_state = {}
    set_options(token)
    set_global_base_url(viz_state, base_url)

    if ('accessKeyId' in creds) {
        viz_state.aws = new AwsClient({
            accessKeyId: creds.accessKeyId,
            secretAccessKey: creds.secretAccessKey,
            sessionToken: creds.sessionToken,
            region: 'us-east-1',
            service: 's3'
        });

        // fetch after initialization of aws client is apparently required?
        const response = await viz_state.aws.fetch(
          base_url + '/landscape_parameters.json'
        );

        if (!response.ok) {
          throw new Error(`Fetch failed: ${response.statusText}`);
        }

        // const json = await response.json();
        // el.textContent = "Fetch succeeded! Here's the object: " + JSON.stringify(json, null, 2).slice(0,50);


    } else {

        viz_state.aws = null
    }

    viz_state.model = ini_model

    viz_state.img = {}
    viz_state.img.image_layer_colors = {}
    viz_state.img.image_layer_sliders = {}

    await set_landscape_parameters(viz_state.img, base_url)

    await set_dimensions(viz_state, base_url, 'h_and_e')

    viz_state.buttons = {}
    viz_state.buttons.blue = '#8797ff'
    viz_state.buttons.gray = 'gray'
    viz_state.buttons.light_gray = '#EEEEEE'
    viz_state.buttons.buttons = {}

    // move this to landscape_parameters
    // const imgage_name_for_dim = 'dapi'
    const info = {
        name: 'h_and_e',
        color: [0, 0, 255]
    }

    let simple_image_layer = await make_simple_image_layer(viz_state, info)

    let layers_sst = {
        'simple_image_layer': simple_image_layer,
    }

    viz_state.views = set_views()

    let deck_sst = ini_deck_sst(root, width, height)

    const initial_view_state = {
        target: [ini_x, ini_y, ini_z],
        zoom: ini_zoom
    }

    deck_sst.setProps({
        views: viz_state.views,
        layers: [ layers_sst.simple_image_layer ],
        // getTooltip: (info) => make_tile_tooltip(info, viz_state),
        initialViewState: initial_view_state,
    })

    // if (Object.keys(viz_state.model).length > 0) {

    //     // ist version
    //     // viz_state.model.on('change:update_trigger', () => update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state))

    //     viz_state.model.on('change:update_trigger', () => update_tile_landscape_from_cgm(deck_sst, layers_sst, viz_state))
    // }

    // set_tile_layer_onclick(deck_sst, layers_sst, viz_state)

    // const ui_container = make_sst_ui_container(deck_sst, layers_sst, viz_state)

    // UI and Viz Container
    // el.appendChild(ui_container)
    el.appendChild(root)

    return () => deck_sst.finalize()

}