import { set_dict_cell_cats, update_cell_cats } from '../global_variables/cat';
import { is_orbit_technology } from '../global_variables/image_info';
import { update_meta_cluster } from '../global_variables/meta_cluster';
import { buildCellCompactData } from '../utils/compact_data';

export const update_cell_clusters = (deck_ist, layers_obj, viz_state) => {
  const new_cluster_info = viz_state.model.get('cell_clusters');
  const pointCloud = is_orbit_technology(
    viz_state.img?.landscape_parameters?.technology
  );

  update_meta_cluster(viz_state.cats, new_cluster_info['meta_cluster']);
  update_cell_cats(viz_state.cats, new_cluster_info['new_clusters']);
  if (pointCloud) {
    viz_state.cats.dict_cell_cats = {};
    viz_state.cats.has_dict_cell_cats = false;
  } else {
    set_dict_cell_cats(viz_state.cats);
  }

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

  if (!pointCloud) {
    viz_state.combo_data.cell_compact = buildCellCompactData(
      viz_state.cats.cell_names_array,
      viz_state.combo_data.cell_compact?.positions || new Float64Array(),
      viz_state.combo_data.cell_compact?.size || 2,
      viz_state.cats.dict_cell_cats
    );
  }

  if (viz_state.viewport_cache) {
    viz_state.viewport_cache.lastCellBarData = null;
  }
};
