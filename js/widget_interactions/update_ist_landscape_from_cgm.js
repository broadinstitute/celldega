import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_selected_genes } from '../global_variables/selected_genes';
import { handleAsyncError } from '../temp_utils/errorHandler';

export const update_ist_landscape_from_cgm = async (
  deck_ist,
  layers_obj,
  viz_state
) => {
  const raw_click = viz_state.model.get('update_trigger');
  if (!raw_click || typeof raw_click !== 'object') {
    return;
  }

  const click_info = {
    type: raw_click.type || raw_click.click_type,
    value: raw_click.value || raw_click.click_value,
  };

  const click_type = click_info.type?.replace('-', '_');

  if (!click_type) {
    return;
  }

  let inst_gene;
  let new_cat;

  // add try catch block
  try {
    if (click_type === 'row_label') {
      inst_gene = click_info.value.name;

      new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

      update_cat(viz_state.cats, new_cat);
      update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
      // update_selected_cats(viz_state.cats, [], viz_state.obs_store);
      update_selected_cats(
        viz_state.cats,
        new_cat === 'cluster' ? [] : [inst_gene],
        viz_state.obs_store
      );

      // cell by gene data and cell layer refresh handled by selected_genes subscriber
    } else if (click_type === 'col_label') {
      inst_gene = 'cluster';
      new_cat = click_info.value.name;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      // cell layer refresh handled by selected_genes subscriber
    } else if (click_type === 'col_dendro') {
      const new_cats = click_info.value.selected_names;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      // cell layer refresh handled by selected_genes subscriber
    }
  } catch (error) {
    handleAsyncError(error, {
      context: 'updating IST landscape from CGM',
      logUnexpected: true,
      throwOnAuth: false,
    });
  }
};
