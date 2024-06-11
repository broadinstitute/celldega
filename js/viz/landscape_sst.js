import * as d3 from 'd3';
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_views } from '../deck-gl/views.js';
import { set_initial_view_state } from "../deck-gl/initial_view_state.js";
import { deck, set_deck } from '../deck-gl/deck_sst.js'
import { update_layers } from "../deck-gl/layers_sst.js";
import { square_scatter_layer, ini_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";  
import { update_tile_scatter_data } from "../global_variables/tile_scatter_data.js";
import { update_tile_cats_array } from "../global_variables/tile_cats_array.js";
import { update_tile_names_array } from "../global_variables/tile_names_array.js";
import { update_tile_color_dict } from "../global_variables/tile_color_dict.js";
import { set_meta_gene } from "../global_variables/meta_gene.js";
import { set_dimensions } from '../global_variables/image_dimensions.js';
import { set_landscape_parameters } from "../global_variables/landscape_parameters.js";
import { simple_image_layer, make_simple_image_layer } from "../deck-gl/simple_image_layer.js";
import { set_global_base_url } from "../global_variables/global_base_url.js";
import { set_model, model } from "../global_variables/model.js";
import { update_tile_landscape_from_cgm } from "../widget_interactions/update_tile_landscape_from_cgm.js";
import { gene_search, update_gene_search } from '../ui/gene_search.js';

export const landscape_sst = async ( 
    ini_model, 
    el,
    base_url,
    token, 
    ini_x, 
    ini_y, 
    ini_z,
    ini_zoom 
) => {

    // Create a container for the gene search box and additional elements
    let ui_container = document.createElement("div");
    ui_container.style.display = "flex";
    ui_container.style.flexDirection = "row";
    ui_container.style.width = "700px";
    ui_container.style.border = "1px solid #ccc";

    // Create and append the visualization container
    let root = document.createElement("div");
    root.style.height = "800px";        

    set_model(ini_model)

    set_options(token)
    set_global_base_url(base_url)
    await set_landscape_parameters(base_url)
    await set_dimensions(base_url, 'cells' )

    await update_gene_search(base_url, token)

    // move this to landscape_parameters
    // const imgage_name_for_dim = 'dapi'
    const info = { 
        name: 'cells', 
        color: [0, 0, 255]
    }    

    await make_simple_image_layer(info)

    const tile_url = base_url + 'tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)

    update_tile_scatter_data(get_scatter_data(tile_arrow_table))
    update_tile_cats_array(tile_arrow_table.getChild("cluster").toArray())
    update_tile_names_array(tile_arrow_table.getChild("name").toArray())

    await set_meta_gene(base_url)
    await update_tile_color_dict(base_url)
    ini_square_scatter_layer()
    const new_layers = [simple_image_layer, square_scatter_layer]
    await update_layers(new_layers)

    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)    
    update_views()

    set_deck(root)

    console.log('here!!!')

    model.on('change:update_trigger', update_tile_landscape_from_cgm);

    d3.select(ui_container)
        .append('div')
        .attr('class', 'button blue')
        .text('IMG')
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', 'blue')
        .style('margin', '5px')
        .style('user-select', 'none')
        .on('click', function() {
            const current = d3.select(this);
            // Toggle the class between blue and gray
            if (current.style('color') === 'blue') {
                current.style('color', 'gray');
            } else {
                current.style('color', 'blue');
            }
            // You can add additional logic here to handle layer toggling
        }); 

    d3.select(ui_container)
        .append('div')
        .attr('class', 'button blue')
        .text('TILE')
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', 'blue')
        .style('margin', '5px')
        .on('click', function() {
            const current = d3.select(this);
            // Toggle the class between blue and gray
            if (current.style('color') === 'blue') {
                current.style('color', 'gray');
            } else {
                current.style('color', 'blue');
            }
            // You can add additional logic here to handle layer toggling
        });         

    
    ui_container.appendChild(gene_search)

    el.appendChild(ui_container)
    el.appendChild(root);

    return () => deck.finalize();  

}