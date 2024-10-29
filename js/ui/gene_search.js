import * as d3 from 'd3'
import { update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js"
import { update_cat, update_selected_cats } from "../global_variables/cat.js"
// import { deck_sst } from "../deck-gl/deck_sst.js"
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"
import { set_gene_search_input } from "./gene_search_input.js"
// import { simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { update_selected_genes } from "../global_variables/selected_genes.js"
import { update_path_layer_id } from "../deck-gl/path_layer.js"
import { update_cell_layer_id } from "../deck-gl/cell_layer.js"
import { update_trx_layer_id } from "../deck-gl/trx_layer.js"
import { update_cell_exp_array } from "../global_variables/cell_exp_array.js"
import { toggle_image_layers_and_ctrls } from "./ui_containers.js"
import { get_layers_list } from "../deck-gl/layers_ist.js"
import { uniprot_data, uniprot_get_request } from '../external_apis/uniprot_api.js'

let gene_search_options = []

const sst_gene_search_callback = async (deck_sst, viz_state, layers_sst) => {

    const inst_gene = viz_state.genes.gene_search_input.value

    const new_cat = inst_gene === '' ? 'cluster' : inst_gene;

    if (inst_gene === '' || viz_state.genes.gene_names.includes(inst_gene)) {

        update_cat(viz_state.cats, new_cat);
        update_selected_genes(viz_state.genes, inst_gene === '' ? [] : [inst_gene])
        update_selected_cats(viz_state.cats, [])

        if (inst_gene !== '' && gene_search_options.includes(inst_gene)) {
            await update_tile_exp_array(viz_state, inst_gene)
        }

        update_square_scatter_layer(viz_state, layers_sst)
        deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})

        await update_gene_text_box(viz_state.genes, inst_gene)

    }

}

const ist_gene_search_callback = async (deck_ist, layers_obj, viz_state) => {

    const inst_gene = viz_state.genes.gene_search_input.value;

    const new_cat = inst_gene === '' ? 'cluster' : inst_gene;

    if (inst_gene === '' || viz_state.genes.gene_names.includes(inst_gene)) {

        update_cat(viz_state.cats, new_cat);
        update_selected_genes(viz_state.genes, inst_gene === '' ? [] : [inst_gene])
        update_selected_cats(viz_state.cats, [])

        const inst_gene_in_gene_names = viz_state.genes.gene_names.includes(inst_gene)

        if (inst_gene_in_gene_names) {
            await update_cell_exp_array(viz_state.cats, viz_state.genes, viz_state.global_base_url, inst_gene)
        }

        toggle_image_layers_and_ctrls(layers_obj, viz_state, !inst_gene_in_gene_names)

        update_cell_layer_id(layers_obj, new_cat)
        update_path_layer_id(layers_obj, new_cat)
        update_trx_layer_id(viz_state.genes, layers_obj)

        const layers_list = get_layers_list(layers_obj, viz_state.close_up)
        deck_ist.setProps({layers: layers_list})

        const reset_gene = false

        viz_state.genes.svg_bar_gene.selectAll("g")
            .attr('font-weight', 'normal')
            .attr('opacity', reset_gene ? 1.0 : 0.25)

        if (!reset_gene) {

            const selectedBar = viz_state.genes.svg_bar_gene.selectAll("g")
                .filter(function() {
                    return d3.select(this).select("text").text() === inst_gene
                })
                .attr('opacity', 1.0)

            if (!selectedBar.empty()) {
                const barPosition = selectedBar.node().getBoundingClientRect().top
                const containerPosition = viz_state.containers.bar_gene.getBoundingClientRect().top
                const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_gene.scrollTop

                viz_state.containers.bar_gene.scrollTo({
                    top: scrollPosition,
                    behavior: 'smooth'
                })
            }

            await update_gene_text_box(viz_state.genes, inst_gene)

        }

    }
};


export const set_gene_search = async (tech_type, inst_deck, layers_obj, viz_state) => {

    gene_search_options = ['cluster', ...viz_state.genes.gene_names]

    viz_state.genes.gene_search.style.width = "115px"

    set_gene_search_input(viz_state.genes)

    let dataList = document.createElement("datalist")
    dataList.id = 'genes_datalist'
    viz_state.genes.gene_search_input.setAttribute('list', dataList.id)

    // Populate the datalist with gene names
    gene_search_options.forEach(optionText => {
        let option = document.createElement("option")
        option.value = optionText
        dataList.appendChild(option)
    })

    // Apply styles to the input element
    viz_state.genes.gene_search_input.style.width = '156px', // '109px'
    viz_state.genes.gene_search_input.style.maxWidth = "250px"
    viz_state.genes.gene_search_input.style.height = '12px'
    viz_state.genes.gene_search_input.style.fontSize = '12px'
    viz_state.genes.gene_search_input.style.border = '1px solid #d3d3d3'
    viz_state.genes.gene_search_input.style.borderRadius = '0'

    viz_state.genes.gene_search_input.style.display = "inline-block"
    viz_state.genes.gene_search_input.style.padding = "1pt 2pt"

    // Append elements
    viz_state.genes.gene_search.appendChild(viz_state.genes.gene_search_input)
    viz_state.genes.gene_search.appendChild(dataList)

    // Create a div element with some text
    viz_state.genes.gene_text_box = document.createElement('div');
    viz_state.genes.gene_text_box.textContent = ''
    viz_state.genes.gene_text_box.style.marginTop = '3px'
    viz_state.genes.gene_text_box.style.color = '#222222'
    viz_state.genes.gene_text_box.style.border = "1px solid #d3d3d3"
    viz_state.genes.gene_text_box.style.height = '69px' //'71px'
    viz_state.genes.gene_text_box.style.overflow = 'scroll'
    viz_state.genes.gene_text_box.style.fontSize = '12px'
    viz_state.genes.gene_text_box.style.cursor = 'default'
    viz_state.genes.gene_text_box.style.width = '142px'
    viz_state.genes.gene_text_box.style.paddingLeft = '2px'
    viz_state.genes.gene_text_box.style.paddingRight = '17px'

    viz_state.genes.gene_text_box.addEventListener('wheel', (event) => {
        const { scrollTop, scrollHeight, clientHeight } = viz_state.genes.gene_text_box
        const atTop = scrollTop === 0
        const atBottom = scrollTop + clientHeight === scrollHeight

        if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
            event.preventDefault()
        }
    })

    viz_state.genes.gene_search.appendChild(viz_state.genes.gene_text_box); // Append the new div with text

    // Set initial default value to "cluster"
    viz_state.genes.gene_search_input.value = ''
    update_cat(viz_state.cats, 'cluster')

    // Event listener when an option is selected or the input is cleared
    let callback
    if (tech_type === 'sst'){

        callback = () => sst_gene_search_callback(inst_deck, viz_state, layers_obj)
        viz_state.genes.gene_search_input.style.marginTop = "10px"
        viz_state.genes.gene_search.style.height = "50px"
    } else {
        callback = () => ist_gene_search_callback(inst_deck, layers_obj, viz_state)
        viz_state.genes.gene_search_input.style.marginTop = "5px"
    }

    viz_state.genes.gene_search_input.addEventListener('input', callback)
}

export const update_gene_text_box = async (genes, inst_gene) => {

    if (inst_gene !== ''){
        genes.gene_text_box.textContent = 'loading'

        await uniprot_get_request(inst_gene)

        const gene_data = uniprot_data[inst_gene]

        if (gene_data && gene_data.name && gene_data.description) {
            genes.gene_text_box.innerHTML = `<span style="color: blue;">${gene_data.name}</span><br>${gene_data.description}`;
        } else {
            genes.gene_text_box.textContent = ''
        }
    } else {
        genes.gene_text_box.textContent = ''
    }

    genes.gene_text_box.scrollTo({
        top: 0,
        behavior: 'smooth'
    })
  };
