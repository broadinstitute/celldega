import * as d3 from 'd3'
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js"
import { update_cat } from "../global_variables/cat.js"
import { deck_sst } from "../deck-gl/deck_sst.js"
import { deck_ist } from "../deck-gl/deck_ist.js"
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"
import { gene_search_input, set_gene_search_input } from "./gene_search_input.js"
import { simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { gene_names } from "../global_variables/gene_names.js"
import { global_base_url } from "../global_variables/global_base_url.js"
import { update_selected_genes } from "../global_variables/selected_genes.js"
import { background_layer } from "../deck-gl/background_layer.js"
import { image_layers, toggle_visibility_image_layers } from "../deck-gl/image_layers.js"
import { path_layer } from "../deck-gl/path_layer.js"
import { cell_layer, update_cell_layer_id } from "../deck-gl/cell_layer.js"
import { trx_layer, update_trx_layer_filter } from "../deck-gl/trx_layer.js"
import { update_cell_exp_array } from "../global_variables/cell_exp_array.js"
import { close_up } from "../global_variables/close_up.js"
import { image_container } from "./ui_containers.js"
import { image_layer_sliders, toggle_slider } from './sliders.js'

export let gene_search = document.createElement("div")

let gene_search_options = []

let new_layers = []

const toggle_image_layers_and_ctrls = (is_visible) => {
    d3.select(image_container)
        .selectAll('.img_layer_button')
        .style('color', is_visible ? 'blue' : 'gray');

    image_layer_sliders.map(slider => toggle_slider(slider, is_visible))
    toggle_visibility_image_layers(is_visible)
}

const sst_gene_search_callback = async () => {

    const inst_gene = gene_search_input.value;
    const new_cat = inst_gene === '' ? 'cluster' : inst_gene;
    update_cat(new_cat);

    if (inst_gene !== '' && gene_search_options.includes(inst_gene)) {
        await update_tile_exp_array(global_base_url, inst_gene);
    }

    update_square_scatter_layer();
    deck_sst.setProps({layers: [simple_image_layer, square_scatter_layer]});
};

const ist_gene_search_callback = async () => {
    const inst_gene = gene_search_input.value;
    const new_cat = inst_gene === '' ? 'cluster' : inst_gene;

    if (inst_gene === '' || gene_names.includes(inst_gene)) {

        update_cat(new_cat);
        update_selected_genes(inst_gene === '' ? [] : [inst_gene]);

        if (gene_names.includes(inst_gene)) {
            await update_cell_exp_array(global_base_url, inst_gene)

            // const is_visible = false

            // d3.select(image_container)
            //     .selectAll('.img_layer_button')
            //     .style('color', is_visible ? 'blue' : 'gray');

            // image_layer_sliders.map(slider => toggle_slider(slider, is_visible))
            // toggle_visibility_image_layers(is_visible)

            toggle_image_layers_and_ctrls(false)

        } else {
            // const is_visible = true

            // d3.select(image_container)
            //     .selectAll('.img_layer_button')
            //     .style('color', is_visible ? 'blue' : 'gray');

            // image_layer_sliders.map(slider => toggle_slider(slider, is_visible))
            // toggle_visibility_image_layers(is_visible)

            toggle_image_layers_and_ctrls(true)
        }

        update_cell_layer_id(new_cat)
        update_trx_layer_filter()

        if (close_up){
            new_layers = [
                background_layer,
                ...image_layers,
                path_layer,
                cell_layer,
                trx_layer
            ]
        } else {
            new_layers = [
                background_layer,
                ...image_layers,
                cell_layer,
            ]
        }

        deck_ist.setProps({
            layers: new_layers
        });
    }
};


export const set_gene_search = async (tech_type) => {

    gene_search_options = ['cluster', ...gene_names]

    gene_search.style.width = "250px"

    set_gene_search_input()

    let dataList = document.createElement("datalist")
    dataList.id = 'genes_datalist'
    gene_search_input.setAttribute('list', dataList.id)

    // Populate the datalist with gene names
    gene_search_options.forEach(optionText => {
        let option = document.createElement("option")
        option.value = optionText
        dataList.appendChild(option)
    })

    // Apply styles to the input element
    gene_search_input.style.width = '100px' // "100%"
    gene_search_input.style.maxWidth = "250px"
    gene_search_input.style.height = "20px"


    gene_search_input.style.display = "inline-block"
    gene_search_input.style.padding = "1pt 2pt"

    // Append elements
    gene_search.appendChild(gene_search_input)
    gene_search.appendChild(dataList)

    // Set initial default value to "cluster"
    gene_search_input.value = ''
    update_cat('cluster')

    // Event listener when an option is selected or the input is cleared
    let callback
    if (tech_type === 'sst'){
        callback = sst_gene_search_callback
        gene_search_input.style.marginTop = "10px"
        gene_search.style.height = "50px"
    } else {
        callback = ist_gene_search_callback
        gene_search_input.style.marginTop = "5px"
        // gene_search.style.height = "25px"
    }

    gene_search_input.addEventListener('input', callback)
}
