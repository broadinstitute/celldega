import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';
import { handleAsyncError } from '../temp_utils/errorHandler';

export const update_ist_landscape_from_cgm = async (
  deck_ist,
  layers_obj,
  viz_state
) => {
  const click_info = viz_state.model.get('update_trigger');

  let inst_gene;
  let new_cat;

  // add try catch block
  try {
    if (click_info.type === 'row_label') {
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

      await update_cell_exp_array(
        viz_state.cats,
        viz_state.genes,
        viz_state.global_base_url,
        inst_gene,
        viz_state.seg.version,
        viz_state.vector_name_integer,
        viz_state.aws
      );

      viz_state.layers_obj = layers_obj;

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: true,
      });
    } else if (click_info.type === 'col_label') {
      inst_gene = 'cluster';
      new_cat = click_info.value.name;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      viz_state.layers_obj = layers_obj;

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: true,
      });
    } else if (click_info.type === 'col_dendro') {
      inst_gene = 'cluster';

      inst_gene = 'cluster';
      const new_cats = click_info.value.selected_names;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      viz_state.layers_obj = layers_obj;

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: true,
      });

      update_cat(viz_state.cats, inst_gene);
      update_selected_cats(
        viz_state.cats,
        click_info.click_value,
        viz_state.obs_store
      );
    }
  } catch (error) {
    handleAsyncError(error, {
      context: 'updating IST landscape from CGM',
      logUnexpected: true,
      throwOnAuth: false,
    });
  }
};
