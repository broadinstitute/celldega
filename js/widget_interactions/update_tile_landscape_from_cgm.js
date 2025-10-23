// import { model } from '../global_variables/model'
import { update_square_scatter_layer } from '../deck-gl/layers/square_scatter_layer';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_selected_genes } from '../global_variables/selected_genes';
import { update_selected_proteins } from '../global_variables/selected_proteins';
import { update_tile_exp_array } from '../global_variables/tile_exp_array';

export const update_tile_landscape_from_cgm = async (
  deck_sst,
  layers_sst,
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

  // legacy click names sometimes use dashes
  const click_type = click_info.type?.replace('-', '_');

  if (!click_type) {
    return;
  }

  let inst_gene;

  if (click_type === 'row_label') {
    inst_gene = click_info.value.name || click_info.value;
    update_cat(viz_state.cats, inst_gene);
    await update_tile_exp_array(viz_state, inst_gene);
    update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
    update_selected_proteins(viz_state.proteins, [], viz_state.obs_store);

    if (viz_state.genes && viz_state.genes.gene_search_input) {
      viz_state.genes.gene_search_input.value = inst_gene;
    }
  } else if (click_type === 'col_label') {
    update_cat(viz_state.cats, 'cluster');
    update_selected_cats(
      viz_state.cats,
      [click_info.value.name || click_info.value],
      viz_state.obs_store
    );
    update_selected_genes(viz_state.genes, [], viz_state.obs_store);
    update_selected_proteins(viz_state.proteins, [], viz_state.obs_store);
  } else if (click_type === 'col_dendro') {
    update_cat(viz_state.cats, 'cluster');
    update_selected_cats(
      viz_state.cats,
      click_info.value.selected_names || click_info.value,
      viz_state.obs_store
    );
    update_selected_genes(viz_state.genes, [], viz_state.obs_store);
    update_selected_proteins(viz_state.proteins, [], viz_state.obs_store);
  } else {
    update_cat(viz_state.cats, 'cluster');
    update_selected_genes(viz_state.genes, [], viz_state.obs_store);
    update_selected_proteins(viz_state.proteins, [], viz_state.obs_store);
  }

  update_square_scatter_layer(viz_state, layers_sst);
  deck_sst.setProps({
    layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer],
  });
};
