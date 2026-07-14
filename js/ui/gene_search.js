import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';

import { set_gene_search_input } from './gene_search_input';

let gene_search_options = [];
let gene_datalist_counter = 0;

const ist_gene_search_callback = async (deck_ist, layers_obj, viz_state) => {
  const inst_gene = viz_state.genes.gene_search_input.value;

  const new_cat = inst_gene === '' ? 'cluster' : inst_gene;

  if (inst_gene === '' || viz_state.genes.gene_names.includes(inst_gene)) {
    update_cat(viz_state.cats, new_cat);

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: false,
      trx_layer: false,
    });

    update_selected_genes(
      viz_state.genes,
      inst_gene === '' ? [] : [inst_gene],
      viz_state.obs_store
    );

    const inst_gene_in_gene_names =
      viz_state.genes.gene_names.includes(inst_gene);

    if (inst_gene_in_gene_names) {
      await update_cell_exp_array(
        viz_state.cats,
        viz_state.genes,
        viz_state.global_base_url,
        inst_gene,
        viz_state.seg.version,
        viz_state.vector_name_integer,
        viz_state.aws,
        viz_state.row_group_readers?.cbg
      );
    }

    // make selected_cats an empty array if new_cat is cluster or
    // make it an array with the selected gene if inst_gene is not an empty string
    // update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
    //
    // update selected_cats after update_cell_exp_array has been run
    // can clean up and move more logic to observability
    update_selected_cats(
      viz_state.cats,
      new_cat === 'cluster' ? [] : [inst_gene],
      viz_state.obs_store
    );
  }
};

export const set_gene_search = async (
  _tech_type,
  inst_deck,
  layers_obj,
  viz_state
) => {
  gene_search_options = ['cluster', ...viz_state.genes.gene_names];

  viz_state.genes.gene_search.style.width = '115px';

  set_gene_search_input(viz_state.genes);

  const dataList = document.createElement('datalist');
  // Use unique ID to prevent contamination between multiple Landscape instances
  gene_datalist_counter += 1;
  dataList.id = `genes_datalist_${gene_datalist_counter}_${Date.now()}`;
  viz_state.genes.gene_search_input.setAttribute('list', dataList.id);

  // Populate the datalist with gene names
  gene_search_options.forEach((optionText) => {
    const option = document.createElement('option');
    option.value = optionText;
    dataList.appendChild(option);
  });

  // Apply styles to the input element
  viz_state.genes.gene_search_input.style.width = '156px'; // '109px'
  viz_state.genes.gene_search_input.style.maxWidth = '250px';
  viz_state.genes.gene_search_input.style.height = '12px';
  viz_state.genes.gene_search_input.style.fontSize = '12px';
  viz_state.genes.gene_search_input.style.border = '1px solid #d3d3d3';
  viz_state.genes.gene_search_input.style.borderRadius = '0';

  viz_state.genes.gene_search_input.style.display = 'inline-block';
  viz_state.genes.gene_search_input.style.padding = '1pt 2pt';

  // Append elements
  viz_state.genes.gene_search.appendChild(viz_state.genes.gene_search_input);
  viz_state.genes.gene_search.appendChild(dataList);

  // Create a div element with some text
  viz_state.genes.gene_text_box = document.createElement('div');
  viz_state.genes.gene_text_box.textContent = '';
  viz_state.genes.gene_text_box.style.marginTop = '3px';
  viz_state.genes.gene_text_box.style.color = '#222222';
  viz_state.genes.gene_text_box.style.border = '1px solid #d3d3d3';
  viz_state.genes.gene_text_box.style.height = '69px'; //'71px'
  viz_state.genes.gene_text_box.style.overflow = 'scroll';
  viz_state.genes.gene_text_box.style.fontSize = '12px';
  viz_state.genes.gene_text_box.style.cursor = 'default';
  viz_state.genes.gene_text_box.style.width = '142px';
  viz_state.genes.gene_text_box.style.paddingLeft = '2px';
  viz_state.genes.gene_text_box.style.paddingRight = '17px';

  viz_state.genes.gene_text_box.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } =
      viz_state.genes.gene_text_box;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  viz_state.genes.gene_search.appendChild(viz_state.genes.gene_text_box); // Append the new div with text

  // Set initial default value to "cluster"
  viz_state.genes.gene_search_input.value = '';
  update_cat(viz_state.cats, 'cluster');

  // Event listener when an option is selected or the input is cleared
  const callback = () =>
    ist_gene_search_callback(inst_deck, layers_obj, viz_state);
  viz_state.genes.gene_search_input.style.marginTop = '5px';

  viz_state.genes.gene_search_input.addEventListener('input', callback);
};
