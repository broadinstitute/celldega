import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_tile_cat } from "../global_variables/tile_cat.js" 
import { deck } from "../deck-gl/deck_sst.js";
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"; 
import { input, set_input } from "./input.js";
import { simple_image_layer } from "../deck-gl/simple_image_layer.js";

export let gene_search = document.createElement("div");

export const update_gene_search = async (base_url, token) => {
    set_options(token);

    let meta_gene_table = await get_arrow_table(base_url + 'meta_gene.parquet', options.fetch);

    let all_genes = meta_gene_table.getChild('__index_level_0__').toArray().sort();
    const gene_search_options = ['cluster', ...all_genes];

    gene_search.style.height = "50px";
    gene_search.style.width = "250px";

    set_input()

    let dataList = document.createElement("datalist");
    dataList.id = 'genes_datalist'; 
    input.setAttribute('list', dataList.id); 

    // Populate the datalist with gene names
    gene_search_options.forEach(optionText => {
        let option = document.createElement("option");
        option.value = optionText;
        dataList.appendChild(option);
    });

    // Apply styles to the input element
    input.style.width = "100%";
    input.style.maxWidth = "250px"; 
    input.style.height = "20px"; 
    input.style.marginTop = "10px";
    input.style.display = "inline-block";
    input.style.padding = "1pt 2pt";    

    // Append elements
    gene_search.appendChild(input);
    gene_search.appendChild(dataList);

    // Set initial default value to "cluster"
    input.value = '';
    update_tile_cat('cluster');

    // Event listener when an option is selected or the input is cleared
    input.addEventListener('input', async function() {
        const selected_gene = input.value;
        if (selected_gene === '') {
            // If the input is empty, set it to 'cluster' and update
            update_tile_cat('cluster')
        } else if (gene_search_options.includes(selected_gene)) {

            console.log('updating becuase of new gene search')
            update_tile_cat(selected_gene)
            await update_tile_exp_array(base_url, selected_gene)
        }
        update_square_scatter_layer()
        deck.setProps({layers: [simple_image_layer, square_scatter_layer]})        
    });
};
