// Applying a rank view to the live deck.
//
// State handling lives in ../../matrix/rank_views.js; this is the deck-side
// orchestration. It deliberately reuses the crop path's layer rebuild, because
// a rank view narrows exactly the same axis filter a crop does -- the two are
// intersected in crop_filter.js, so a brush crop inside a view keeps working.

import * as d3 from 'd3';

import {
  refresh_rank_view_dendro,
  resolve_rank_view_level,
  set_rank_view_state,
} from '../../matrix/rank_views';
import { deselect_reorder_buttons } from '../../ui/text_buttons';

import { refresh_filtered_layers, reset_view_to_filter } from './crop';
import { get_mat_layers_list } from './matrix_layers';

/**
 * Mark both axes as clust-ordered in the reorder buttons. A rank view *is* a
 * re-biclustering, so it resets the order the way Clustergrammer's recluster
 * did -- otherwise the view's dendrogram would be hidden behind a stale
 * sum/var ordering.
 *
 * @param {object} viz_state - Visualization state.
 */
const reset_order_to_clust = (viz_state) => {
  ['row', 'col'].forEach((axis) => {
    viz_state.order.current[axis] = 'clust';
    deselect_reorder_buttons(viz_state, axis);

    const button = d3
      .select(viz_state.el)
      .selectAll(`.button-${axis}`)
      .filter(function () {
        return d3.select(this).text().toLowerCase() === 'clust';
      });

    button
      .classed('active', true)
      .style('color', viz_state.buttons.text_active);
  });

  viz_state.labels.reorder_driver = null;
};

/**
 * Switch to a precomputed rank view (or back to the full matrix).
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {number|null} level - Requested row count; snapped to an available
 *   level, with null (or anything past the coarsest level) meaning "all".
 * @returns {boolean} Whether the view actually changed.
 */
export const apply_rank_view = (deck_mat, layers_mat, viz_state, level) => {
  const target = resolve_rank_view_level(viz_state, level);
  if (!set_rank_view_state(viz_state, target)) return false;

  // Geometry changes wholesale here, so mint a fresh body layer rather than
  // letting deck.gl try to tween between two unrelated row sets.
  viz_state.mat._body_layer_rev = (viz_state.mat._body_layer_rev || 0) + 1;

  refresh_rank_view_dendro(viz_state);
  reset_order_to_clust(viz_state);
  refresh_filtered_layers(deck_mat, layers_mat, viz_state);
  reset_view_to_filter(deck_mat, layers_mat, viz_state, {
    snap_annotations: true,
  });

  viz_state.crop?.refresh_controls?.();

  if (viz_state.model?.set) {
    viz_state.model.set('rank_dim', target == null ? 0 : target);
    viz_state.model.save_changes();
  }

  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
  return true;
};
