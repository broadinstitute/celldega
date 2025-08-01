// import { model } from '../global_variables/model'
import { update_square_scatter_layer } from '../deck-gl/layers/square_scatter_layer';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_tile_exp_array } from '../global_variables/tile_exp_array';

export const update_tile_landscape_from_cgm = async (
  deck_sst,
  layers_sst,
  viz_state
) => {
  const click_info = viz_state.model.get('update_trigger');

  let inst_gene;

  if (click_info.click_type === 'row-label') {
    inst_gene = click_info.click_value;
    update_cat(viz_state.cats, inst_gene);
    await update_tile_exp_array(viz_state, inst_gene);
    if (viz_state.genes && viz_state.genes.gene_search_input) {
      viz_state.genes.gene_search_input.value = inst_gene;
    }
  } else if (click_info.click_type === 'col-label') {
    update_cat(viz_state.cats, 'cluster');
    update_selected_cats(
      viz_state.cats,
      [click_info.click_value],
      viz_state.obs_store
    );
  } else if (click_info.click_type === 'col-dendro') {
    update_cat(viz_state.cats, 'cluster');
    update_selected_cats(
      viz_state.cats,
      click_info.click_value,
      viz_state.obs_store
    );
  } else {
    update_cat('cluster');
  }

  update_square_scatter_layer(viz_state, layers_sst);
  deck_sst.setProps({
    layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer],
  });
};
