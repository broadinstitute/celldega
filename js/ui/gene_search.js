import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_tile_cat } from "../global_variables/tile_cat.js"; 
import { deck } from "../deck-gl/toy_deck.js";
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"; 

export let gene_search = document.createElement("div");

export const update_gene_search = async (base_url) => {
    set_options('');

    let meta_gene_table = await get_arrow_table(base_url + 'meta_gene.parquet', options.fetch);

    let all_genes = meta_gene_table.getChild('__index_level_0__').toArray().sort();
    const gene_search_options = ['cluster', ...all_genes];

    gene_search.style.height = "50px";

    // Create an input field with a datalist for autocomplete
    let input = document.createElement("input");
    input.setAttribute('type', 'text');
    input.setAttribute('placeholder', 'Search gene');
    input.style.width = "500px";
    input.style.height = "20px"; // Adjusted for input size
    input.style.marginTop = "5px";
    input.style.display = "inline-block";
    input.style.padding = "1pt 2pt";

    let dataList = document.createElement("datalist");
    dataList.id = 'genes_datalist'; // Unique ID for datalist
    input.setAttribute('list', dataList.id); // Link datalist to input

    // Populate the datalist with gene names
    gene_search_options.forEach(optionText => {
        let option = document.createElement("option");
        option.value = optionText;
        dataList.appendChild(option);
    });

    // Append elements
    gene_search.appendChild(input);
    gene_search.appendChild(dataList);

    // Set initial default value to "cluster"
    input.value = '';
    update_tile_cat('cluster');

    // Event listener when an option is selected or the input is cleared
    input.addEventListener('input', async function() {
        const selectedGene = input.value;
        if (selectedGene === '') {
            // If the input is empty, set it to 'cluster' and update
            update_tile_cat('cluster');
            update_square_scatter_layer();
            deck.setProps({layers: [square_scatter_layer]});
        } else if (gene_search_options.includes(selectedGene)) {
            update_tile_cat(selectedGene);
            await update_tile_exp_array(base_url, selectedGene);
            update_square_scatter_layer();
            deck.setProps({layers: [square_scatter_layer]});
        }
    });
};
