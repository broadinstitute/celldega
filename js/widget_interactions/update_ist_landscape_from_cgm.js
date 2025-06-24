import { update_cell_layer_id } from '../deck-gl/layers/cell_layer';
import { update_path_layer_id } from '../deck-gl/layers/path_layer';
import { update_trx_layer_id } from '../deck-gl/layers/trx_layer';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
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
      update_selected_cats(viz_state.cats, [], viz_state.obs_store);
      await update_cell_exp_array(
        viz_state.cats,
        viz_state.genes,
        viz_state.global_base_url,
        inst_gene,
        viz_state.seg.version,
        viz_state.vector_name_integer,
        viz_state.aws
      );

      update_cell_layer_id(layers_obj, new_cat);
      update_path_layer_id(layers_obj, new_cat);
      update_trx_layer_id(viz_state.genes, layers_obj);

      const layers_list = get_layers_list(layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: layers_list });

    } else if (click_info.type === 'col_label') {
      inst_gene = 'cluster';
      new_cat = click_info.value.name;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      const inst_cat_name = viz_state.cats.selected_cats.join('-');

      update_cell_layer_id(layers_obj, inst_cat_name);
      update_path_layer_id(layers_obj, inst_cat_name);
      update_trx_layer_id(viz_state.genes, layers_obj);

      const layers_list = get_layers_list(layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: layers_list });

    } else if (click_info.type === 'col_dendro') {
      inst_gene = 'cluster';

      inst_gene = 'cluster';
      const new_cats = click_info.value.selected_names;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      const inst_cat_name = viz_state.cats.selected_cats.join('-');

      update_cell_layer_id(layers_obj, inst_cat_name);
      update_path_layer_id(layers_obj, inst_cat_name);
      update_trx_layer_id(viz_state.genes, layers_obj);

      const layers_list = get_layers_list(layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: layers_list });

      update_cat(viz_state.cats, inst_gene);
      update_selected_cats(viz_state.cats, click_info.click_value, viz_state.obs_store);
    }
  } catch (error) {
    handleAsyncError(error, {
      context: 'updating IST landscape from CGM',
      logUnexpected: true,
      throwOnAuth: false,
    });
  }
};
