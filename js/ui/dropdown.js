import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_tile_cat } from "../global_variables/tile_cat"; 
import { deck } from "../deck-gl/toy_deck";

export let dropdown = document.createElement("div");

export const update_dropdown = async (base_url) => {

    set_options('')

    let meta_gene_table = await get_arrow_table(base_url + 'meta_gene.parquet', options.fetch)

    const dropdown_options = meta_gene_table.getChild('__index_level_0__').toArray()

    // Create a dropdown container
    
    dropdown.style.height = "50px";

    // Create a select element
    let select = document.createElement("select");
    select.style.width = "500px";
    select.style.height = "100%";

    update_tile_cat('cluster')

    // Populate the dropdown with options
    dropdown_options.forEach(optionText => {
        let option = document.createElement("option");
        option.value = optionText;
        option.text = optionText;
        select.appendChild(option);
    });

    // Append the select element to the dropdown container
    dropdown.appendChild(select);

    // Handle dropdown change
    select.onchange = async function() {
        console.log('Selected:', select.value);

        update_tile_cat(select.value)

        update_square_scatter_layer()

        deck.setProps({layers: [square_scatter_layer]});

        console.log('trying to update deck.setProps')

    };

}