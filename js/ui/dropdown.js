import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_tile_cat } from "../global_variables/tile_cat"; 
import { deck } from "../deck-gl/toy_deck";
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"; 

export let dropdown = document.createElement("div");

// export const update_dropdown = async (base_url) => {

//     set_options('')

//     let meta_gene_table = await get_arrow_table(base_url + 'meta_gene.parquet', options.fetch)

//     let all_genes = meta_gene_table.getChild('__index_level_0__').toArray().sort()
//     const dropdown_options = ['cluster', ...all_genes];

//     dropdown.style.height = "50px";

//     let select = document.createElement("select");
//     select.style.width = "500px";
//     select.style.height = "100%";

//     update_tile_cat('cluster')

//     dropdown_options.forEach(optionText => {
//         let option = document.createElement("option");
//         option.value = optionText;
//         option.text = optionText;
//         select.appendChild(option);
//     });

//     // dropdown.appendChild(select);

//     // select.onchange = async function() {
//     //     const inst_gene = select.value
//     //     update_tile_cat(inst_gene)
//     //     await update_tile_exp_array(base_url, inst_gene)
//     //     update_square_scatter_layer()
//     //     deck.setProps({layers: [square_scatter_layer]});
//     // };

// }


// export const update_dropdown = async (base_url) => {
//     set_options('');

//     let meta_gene_table = await get_arrow_table(base_url + 'meta_gene.parquet', options.fetch);

//     let all_genes = meta_gene_table.getChild('__index_level_0__').toArray().sort();
//     const dropdown_options = ['cluster', ...all_genes];

//     dropdown.style.height = "50px";

//     // Create an input field with a datalist for autocomplete
//     let input = document.createElement("input");
//     input.setAttribute('type', 'text');
//     input.setAttribute('placeholder', 'Search gene');
//     input.style.width = "500px";
//     input.style.height = "20px"; // Adjusted for input size
//     input.style.marginTop = "5px";
//     input.style.display = "inline-block";
//     input.style.padding = "1pt 2pt";

//     let dataList = document.createElement("datalist");
//     dataList.id = 'genes_datalist'; // Unique ID for datalist
//     input.setAttribute('list', dataList.id); // Link datalist to input

//     // Populate the datalist with gene names
//     dropdown_options.forEach(optionText => {
//         let option = document.createElement("option");
//         option.value = optionText;
//         dataList.appendChild(option);
//     });

//     // Append elements
//     dropdown.appendChild(input);
//     dropdown.appendChild(dataList);

//     update_tile_cat('cluster')

//     // Event listener when an option is selected
//     input.addEventListener('input', async function() {
//         const selectedGene = input.value;
//         if (dropdown_options.includes(selectedGene)) {
//             console.log('Selected:', selectedGene);
//             update_tile_cat(selectedGene);
//             await update_tile_exp_array(base_url, selectedGene);
//             update_square_scatter_layer();
//             deck.setProps({layers: [square_scatter_layer]});
//             console.log('trying to update deck.setProps');
//         }
//     });
// };


export const update_dropdown = async (base_url) => {
    set_options('');

    let meta_gene_table = await get_arrow_table(base_url + 'meta_gene.parquet', options.fetch);

    let all_genes = meta_gene_table.getChild('__index_level_0__').toArray().sort();
    const dropdown_options = ['cluster', ...all_genes];

    dropdown.style.height = "50px";

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
    dropdown_options.forEach(optionText => {
        let option = document.createElement("option");
        option.value = optionText;
        dataList.appendChild(option);
    });

    // Append elements
    dropdown.appendChild(input);
    dropdown.appendChild(dataList);

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
        } else if (dropdown_options.includes(selectedGene)) {
            update_tile_cat(selectedGene);
            await update_tile_exp_array(base_url, selectedGene);
            update_square_scatter_layer();
            deck.setProps({layers: [square_scatter_layer]});
        }
    });
};
