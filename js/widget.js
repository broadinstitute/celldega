/* eslint-disable no-unused-vars */

import "./widget.css";
import { landscape } from "./viz/landscape";
import { landscape_sst } from "./viz/landscape_sst";
import { gene_search, update_gene_search } from "./ui/gene_search";
import cgm from 'clustergrammer-gl';
import _ from 'underscore';
// import * as d3 from 'd3';

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
        console.log('rendering Visium-HD')
        return render_landscape_sst({ model, el });
    }

}

export const render_landscape_ist = async ({ model, el }) => {

    const token = model.get('token_traitlet')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');    
    const ini_z = model.get('ini_z');    
    const ini_zoom = model.get('ini_zoom');
    const base_url = model.get('base_url')

    // Create and append the visualization.
    let root = document.createElement("div");
    root.style.height = "800px";
    el.appendChild(root); 

    return landscape(
        token, 
        ini_x, 
        ini_y, 
        ini_z,
        ini_zoom, 
        base_url, 
        root
    )

}

export const render_landscape_sst = async ({ model, el }) => {
    
    const token = model.get('token_traitlet')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');    
    const ini_z = model.get('ini_z');    
    const ini_zoom = model.get('ini_zoom');
    const base_url = model.get('base_url')

    // Create a container for the gene search box and additional elements
    let ui_container = document.createElement("div");
    ui_container.style.display = "flex";
    ui_container.style.flexDirection = "row";
    ui_container.style.width = "700px";
    ui_container.style.border = "1px solid #ccc";

    // d3.select(ui_container)
    //     .append('div')
    //     .attr('class', 'button blue')
    //     .text('IMG')
    //     .style('cursor', 'pointer')
    //     .style('font-size', '16px')
    //     .style('font-weight', 'bold')
    //     .style('color', 'blue')
    //     .style('margin', '5px')
    //     .style('user-select', 'none')
    //     .on('click', function() {
    //         const current = d3.select(this);
    //         // Toggle the class between blue and gray
    //         if (current.style('color') === 'blue') {
    //             current.style('color', 'gray');
    //         } else {
    //             current.style('color', 'blue');
    //         }
    //         // You can add additional logic here to handle layer toggling
    //     }); 

    // d3.select(ui_container)
    //     .append('div')
    //     .attr('class', 'button blue')
    //     .text('TILE')
    //     .style('cursor', 'pointer')
    //     .style('font-size', '16px')
    //     .style('font-weight', 'bold')
    //     .style('color', 'blue')
    //     .style('margin', '5px')
    //     .on('click', function() {
    //         const current = d3.select(this);
    //         // Toggle the class between blue and gray
    //         if (current.style('color') === 'blue') {
    //             current.style('color', 'gray');
    //         } else {
    //             current.style('color', 'blue');
    //         }
    //         // You can add additional logic here to handle layer toggling
    //     });         

    
    


    // Create and append the visualization container
    let root = document.createElement("div");
    root.style.height = "800px";    
    
    landscape_sst(
        model, 
        root,  
        ui_container,       
        base_url,
        token, 
        ini_x, 
        ini_y, 
        ini_z,
        ini_zoom,
    )

    await update_gene_search(base_url, token)
    ui_container.appendChild(gene_search)

    el.appendChild(ui_container)
    el.appendChild(root);

    return
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

        // fix the row search container
        ///////////////////////////////
        // Function to apply the margin left style
        function applyMarginLeftStyle() {
            var elements = document.querySelectorAll('.row_search_container');
            elements.forEach(function(el) {
                el.style.marginLeft = '800px';
            });
        }
    
        setTimeout(applyMarginLeftStyle, 3000); 
        ///////////////////////////////////        

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
        default:
            throw new Error(`Unknown component type: ${componentType}`);
    }
};
  

export default { render, landscape };
