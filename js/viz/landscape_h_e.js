
import { set_landscape_parameters } from "../global_variables/landscape_parameters.js"
import { options, set_options } from '../global_variables/fetch_options.js'
import { set_global_base_url } from "../global_variables/global_base_url.js"
import { set_dimensions } from '../global_variables/image_dimensions.js'
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
    square_tile_size = 1.4,
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
    root.style.height = "   800px"

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

    console.log('before set_dimensions')
    console.log(viz_state, base_url)

    await set_dimensions(viz_state, base_url, 'h_and_e')

}