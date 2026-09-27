import { update_dendro_layer_data } from '../deck-gl/matrix/dendro_layers';
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers';
import { has_axis_crop_filter } from '../matrix/crop_filter';
import {
  alt_slice_linkage,
  calc_dendro_polygons,
  calc_dendro_triangles,
} from '../matrix/dendro';

import { set_slider_value } from './sliders';

/** Apply a Dendro slider input to one matrix axis. */
export const update_dendro_from_slider = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  event
) => {
  // A crop pins the exact dendrogram slice used to create it. A RANK view is
  // also represented as an axis filter, but has its own linkage and must keep
  // the Dendro slider interactive.
  if (has_axis_crop_filter(viz_state, axis)) {
    set_slider_value(
      event.target,
      viz_state.dendro.sliders[`${axis}_percent`] ?? 50
    );
    return false;
  }

  viz_state.dendro.sliders[`${axis}_percent`] = event.target.value;
  viz_state.dendro.sliders[`${axis}_value`] =
    (viz_state.dendro.max_linkage_dist[axis] * event.target.value) / 100;

  alt_slice_linkage(viz_state, axis, viz_state.dendro.sliders[`${axis}_value`]);
  calc_dendro_triangles(viz_state, axis);
  calc_dendro_polygons(viz_state, axis);
  update_dendro_layer_data(layers_mat, viz_state, axis);
  viz_state.dendro.tree_overlay?.refresh();

  deck_mat.setProps({
    layers: get_mat_layers_list(layers_mat),
  });
  return true;
};
