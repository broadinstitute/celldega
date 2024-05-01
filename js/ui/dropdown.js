import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer";
import { update_tile_cat } from "../global_variables/tile_cat"; 
import { deck } from "../deck-gl/toy_deck";

export let dropdown = document.createElement("div");

export const update_dropdown = (options) => {

    // Create a dropdown container
    
    dropdown.style.height = "50px";

    // Create a select element
    let select = document.createElement("select");
    select.style.width = "500px";
    select.style.height = "100%";

    update_tile_cat('cluster')

    // Populate the dropdown with options
    options.forEach(optionText => {
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
        
        await update_square_scatter_layer()

        console.log(square_scatter_layer)

        deck.setProps({layers: [square_scatter_layer]});

        console.log('trying to update deck.setProps')

    };

}