/* eslint-disable no-unused-vars */

import "./widget.css";
import { landscape_ist } from "./viz/landscape_ist";
import { landscape_sst } from "./viz/landscape_sst";
import { matrix_viz } from "./viz/matrix_viz";
import cgm, { type } from 'clustergrammer-gl';
import _ from 'underscore';

// Ensure these variables are defined globally
const globalVariables =
  ['mat_data', 'manual_category', 'control_svg', 'run_cluster_container',
  'link_options_container', 'selected_label_container', 'network',
  'max_clust_id', 'new_clust_id', 'ini_value_color', '_', 'organism',
  'num_matches'];

globalVariables.forEach((variableName) => {
    window[variableName] = window[variableName] || {};
});

export const render_landscape = async ({ model, el }) => {

    const technology = model.get('technology')

    if (['MERSCOPE', 'Xenium'].includes(technology)){

        return render_landscape_ist({ model, el });

    } else if (['Visium-HD'].includes(technology)){

        return render_landscape_sst({ model, el });

    }

}

export const render_landscape_ist = async ({ model, el }) => {

    const token = model.get('token')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');
    const ini_z = model.get('ini_z');
    const ini_zoom = model.get('ini_zoom');
    const base_url = model.get('base_url')
    const dataset_name = model.get('dataset_name')
    const width = model.get('width')
    const height = model.get('height')

    return landscape_ist(
        el,
        model,
        token,
        ini_x,
        ini_y,
        ini_z,
        ini_zoom,
        base_url,
        dataset_name,
        0.25,
        width,
        height
    )

}

export const render_landscape_sst = async ({ model, el }) => {

    const token = model.get('token')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');
    const ini_z = model.get('ini_z');
    const ini_zoom = model.get('ini_zoom');
    const base_url = model.get('base_url')
    const dataset_name = model.get('dataset_name')
    const square_tile_size = model.get('square_tile_size')
    const width = model.get('width')
    const height = model.get('height')

    landscape_sst(
        model,
        el,
        base_url,
        token,
        ini_x,
        ini_y,
        ini_z,
        ini_zoom,
        square_tile_size,
        dataset_name,
        width,
        height
    )

}

export const render_matrix_new = async ({ model, el }) => {

    const network = model.get('network')
    const width = model.get('width')
    const height = model.get('height')

    matrix_viz(model, el, network, width, height)

}

export const render_matrix = async ({ model, el }) => {

    var my_widget_callback = function(external_model){

        const click_type = this.params.tooltip.tooltip_type
        var click_value = null

        if (click_type === 'row-label'){
            click_value = this.params.int.mouseover.row.name
        } else if (click_type === 'col-label'){
            click_value = this.params.int.mouseover.col.name
        } else if (click_type === 'col-dendro'){
            click_value = this.params.dendro.selected_clust_names
        } else if (click_type === 'row-dendro'){
            click_value = this.params.dendro.selected_clust_names
        }

        var click_info = {
            'click_type': click_type,
            'click_value': click_value
        }

        // Update the click_info trait in the model with the new value
        model.set('click_info', click_info);
        model.save_changes();

    }

    var network = model.get('network')
    let container = document.createElement("div")
    container.style.height = "1000px";
    container.id = "cgm-container";
    el.appendChild(container)

    setTimeout(function() {

        cgm({
            network: network,
            viz_width: 900,
            viz_height: 900,
            widget_callback: my_widget_callback,
            is_widget: true,
            container: container,
            use_hzome: true
        },
        'yes this is a widget'
        );

    }, 1000)


    // trying to remove old tooltips
    // Select all elements with the class 'cgm-tooltip'
    var elements = document.querySelectorAll('.cgm-tooltip');

    // Loop through the NodeList and remove each element
    elements.forEach(function(element) {
        element.parentNode.removeChild(element);
    });

}

export const render = async ({ model, el }) => {

    const componentType = model.get("component");

    switch (componentType) {
        case "Landscape":
            render_landscape({ model, el });
            break;
        case "Matrix":
            render_matrix({ model, el });
            break;
        case "MatrixNew":
            render_matrix_new({ model, el });
            break;
        default:
            throw new Error(`Unknown component type: ${componentType}`);
    }
};


export default { render, landscape_ist, landscape_sst, matrix_viz };
