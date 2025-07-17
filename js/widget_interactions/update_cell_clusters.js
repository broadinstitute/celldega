import { update_cell_cats } from '../global_variables/cat';
import { update_meta_cluster } from '../global_variables/meta_cluster';

export const update_cell_clusters = (deck_ist, layers_obj, viz_state) => {
  const new_cluster_info = viz_state.model.get('cell_clusters');

  update_meta_cluster(viz_state.cats, new_cluster_info['meta_cluster']);
  update_cell_cats(viz_state.cats, new_cluster_info['new_clusters']);

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
  });

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: true,
    path_layer: true,
  });

  viz_state.combo_data.cell = viz_state.combo_data.cell.map((cell) => ({
    ...cell,
    cat: viz_state.cats.dict_cell_cats[cell.name],
  }));
};
