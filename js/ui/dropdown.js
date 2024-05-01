import { update_tile_cat } from "../global_variables/tile_cat";

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
    select.onchange = function() {
        console.log('Selected:', select.value);

        
        // You can also invoke some function here to update other parts of your visualization
        // based on the selection, for example:
        // updateVisualization(select.value, root, base_url);
    };

}