import * as d3 from 'd3'
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js"
import { cat, update_cat, update_selected_cats } from "../global_variables/cat.js"
import { deck_sst } from "../deck-gl/deck_sst.js"
import { deck_ist } from "../deck-gl/deck_ist.js"
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"
import { gene_search_input, set_gene_search_input } from "./gene_search_input.js"
import { simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { gene_names } from "../global_variables/gene_names.js"
import { global_base_url } from "../global_variables/global_base_url.js"
import { update_selected_genes } from "../global_variables/selected_genes.js"
import { update_path_layer_id } from "../deck-gl/path_layer.js"
import { update_cell_layer_id } from "../deck-gl/cell_layer.js"
import { update_trx_layer_filter } from "../deck-gl/trx_layer.js"
import { update_cell_exp_array } from "../global_variables/cell_exp_array.js"
import { toggle_image_layers_and_ctrls } from "./ui_containers.js"
import { layers_ist, update_layers_ist } from "../deck-gl/layers_ist.js"
import { svg_bar_gene } from "./bar_plot.js"
import { bar_container_gene } from "./bar_plot.js"


export let gene_search = document.createElement("div")

let gene_search_options = []

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
        update_selected_genes(inst_gene === '' ? [] : [inst_gene])
        update_selected_cats([])

        const inst_gene_in_gene_names = gene_names.includes(inst_gene)

        if (inst_gene_in_gene_names) {
            await update_cell_exp_array(global_base_url, inst_gene)
        }

        toggle_image_layers_and_ctrls(!inst_gene_in_gene_names)

        update_cell_layer_id(cat)
        update_path_layer_id(cat)
        update_trx_layer_filter()

        update_layers_ist()

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
        }

        deck_ist.setProps({
            layers: layers_ist
        });
    }
};


export const set_gene_search = async (tech_type) => {

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
    gene_search_input.style.width = '100px' // "100%"
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
