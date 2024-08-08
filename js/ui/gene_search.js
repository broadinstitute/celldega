import * as d3 from 'd3'
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js"
import { update_cat, update_selected_cats } from "../global_variables/cat.js"
import { deck_sst } from "../deck-gl/deck_sst.js"
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"
import { gene_search_input, set_gene_search_input } from "./gene_search_input.js"
import { simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { gene_names } from "../global_variables/gene_names.js"
import { global_base_url } from "../global_variables/global_base_url.js"
import { update_selected_genes } from "../global_variables/selected_genes.js"
import { new_update_path_layer_id } from "../deck-gl/path_layer.js"
import { new_update_cell_layer_id } from "../deck-gl/cell_layer.js"
import { new_update_trx_layer_id } from "../deck-gl/trx_layer.js"
import { update_cell_exp_array } from "../global_variables/cell_exp_array.js"
import { toggle_image_layers_and_ctrls } from "./ui_containers.js"
import { get_layers_list } from "../deck-gl/layers_ist.js"
import { svg_bar_gene } from "./bar_plot.js"
import { bar_container_gene } from "./bar_plot.js"
import { uniprot_data, uniprot_get_request } from '../external_apis/uniprot_api.js'
import { close_up } from '../global_variables/close_up.js'

export let gene_search = document.createElement("div")

export let gene_text_box

let gene_search_options = []

const sst_gene_search_callback = async () => {

    const inst_gene = gene_search_input.value
    const new_cat = inst_gene === '' ? 'cluster' : inst_gene
    update_cat(new_cat)

    if (inst_gene !== '' && gene_search_options.includes(inst_gene)) {
        await update_tile_exp_array(global_base_url, inst_gene)
    }

    update_square_scatter_layer()
    deck_sst.setProps({layers: [simple_image_layer, square_scatter_layer]})

}

const ist_gene_search_callback = async (deck_ist, layers_obj) => {

    const inst_gene = gene_search_input.value;

    const new_cat = inst_gene === '' ? 'cluster' : inst_gene;

    if (inst_gene === '' || gene_names.includes(inst_gene)) {

        update_cat(new_cat);
        update_selected_genes(inst_gene === '' ? [] : [inst_gene])
        update_selected_cats([])

        const inst_gene_in_gene_names = gene_names.includes(inst_gene)

        if (inst_gene_in_gene_names) {
            await update_cell_exp_array(global_base_url, inst_gene)
        }

        toggle_image_layers_and_ctrls(layers_obj, !inst_gene_in_gene_names)

        new_update_cell_layer_id(layers_obj, new_cat)
        new_update_path_layer_id(layers_obj, new_cat)
        new_update_trx_layer_id(layers_obj)

        const layers_list = get_layers_list(layers_obj, close_up)
        deck_ist.setProps({layers: layers_list})

        const reset_gene = false

        svg_bar_gene.selectAll("g")
            .attr('font-weight', 'normal')
            .attr('opacity', reset_gene ? 1.0 : 0.25)

        if (!reset_gene) {

            const selectedBar = svg_bar_gene.selectAll("g")
                .filter(function() {
                    return d3.select(this).select("text").text() === inst_gene
                })
                .attr('opacity', 1.0)

            if (!selectedBar.empty()) {
                const barPosition = selectedBar.node().getBoundingClientRect().top
                const containerPosition = bar_container_gene.getBoundingClientRect().top
                const scrollPosition = barPosition - containerPosition + bar_container_gene.scrollTop

                bar_container_gene.scrollTo({
                    top: scrollPosition,
                    behavior: 'smooth'
                })
            }

            await update_gene_text_box(inst_gene)

        }

    }
};


export const set_gene_search = async (tech_type, deck_ist, layers_obj) => {

    gene_search_options = ['cluster', ...gene_names]

    gene_search.style.width = "115px"

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
    gene_search_input.style.width = '156px', // '109px'
    gene_search_input.style.maxWidth = "250px"
    gene_search_input.style.height = '12px'
    gene_search_input.style.fontSize = '12px'
    gene_search_input.style.border = '1px solid #d3d3d3'
    gene_search_input.style.borderRadius = '0'

    gene_search_input.style.display = "inline-block"
    gene_search_input.style.padding = "1pt 2pt"

    // Append elements
    gene_search.appendChild(gene_search_input)
    gene_search.appendChild(dataList)

    // Create a div element with some text
    gene_text_box = document.createElement('div');
    gene_text_box.textContent = ''
    gene_text_box.style.marginTop = '3px'
    gene_text_box.style.color = '#222222'
    gene_text_box.style.border = "1px solid #d3d3d3"
    gene_text_box.style.height = '69px' //'71px'
    gene_text_box.style.overflow = 'scroll'
    gene_text_box.style.fontSize = '12px'
    gene_text_box.style.cursor = 'default'
    gene_text_box.style.width = '142px'
    gene_text_box.style.paddingLeft = '2px'
    gene_text_box.style.paddingRight = '17px'

    gene_text_box.addEventListener('wheel', (event) => {
        const { scrollTop, scrollHeight, clientHeight } = gene_text_box
        const atTop = scrollTop === 0
        const atBottom = scrollTop + clientHeight === scrollHeight

        if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
            event.preventDefault()
        }
    })

    gene_search.appendChild(gene_text_box); // Append the new div with text

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
        callback = () => ist_gene_search_callback(deck_ist, layers_obj)
        gene_search_input.style.marginTop = "5px"
    }

    gene_search_input.addEventListener('input', callback)
}

export const update_gene_text_box = async (inst_gene) => {

    if (inst_gene !== ''){
        gene_text_box.textContent = 'loading'

        await uniprot_get_request(inst_gene)

        const gene_data = uniprot_data[inst_gene]

        if (gene_data && gene_data.name && gene_data.description) {
            gene_text_box.innerHTML = `<span style="color: blue;">${gene_data.name}</span><br>${gene_data.description}`;
        } else {
            gene_text_box.textContent = ''
        }
    } else {
        gene_text_box.textContent = ''
    }

    gene_text_box.scrollTo({
        top: 0,
        behavior: 'smooth'
    })
  };
