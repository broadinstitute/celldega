// Applying a rank view to the live deck.
//
// State handling lives in ../../matrix/rank_views.js; this is the deck-side
// orchestration. It deliberately reuses the crop path's layer rebuild, because
// a rank view narrows exactly the same axis filter a crop does -- the two are
// intersected in crop_filter.js, so a brush crop inside a view keeps working.

import { is_axis_index_visible } from '../../matrix/crop_filter';
import {
  refresh_rank_view_dendro,
  resolve_rank_view_level,
  set_rank_view_state,
  sync_rank_view_model,
} from '../../matrix/rank_views';
import { deselect_reorder_buttons } from '../../ui/text_buttons';

import {
  clear_crop_for_filter_change,
  refresh_filtered_layers,
  reset_view_to_filter,
  sync_gene_row_crop_selection,
} from './crop';
import { toggle_dendro_layer_visibility } from './dendro_layers';

/**
 * Show an axis's current order in its order dropdown (CUSTOM when a label or
 * attribute reorder is in effect).
 *
 * @param {object} viz_state - Visualization state.
 * @param {string} axis - "row" or "col".
 */
const sync_order_control = (viz_state, axis) => {
  const order = viz_state.order.current[axis];
  if (order === 'custom') {
    deselect_reorder_buttons(viz_state, axis);
    return;
  }
  const dropdown = viz_state.reorder_dropdowns?.[axis];
  if (dropdown) {
    dropdown.value = order;
    dropdown.style.color = viz_state.buttons.text_active;
  }
};

/**
 * Carry each axis's order across a rank-view change instead of resetting it.
 *
 * - CLUST picks up the new view's own bi-clustering.
 * - SUM / VAR / INI and attribute reorders are full-matrix ranks, so the rows
 *   that remain keep their relative order.
 * - A custom order driven by a double-clicked label is also a full-matrix
 *   ranking, so it holds while that label is still in the view (a column label
 *   always is -- views only filter rows). If the driving gene is filtered out,
 *   the order would be keyed on something no longer shown, so that axis falls
 *   back to CLUST.
 *
 * Call after the new view's filter state is set.
 *
 * @param {object} viz_state - Visualization state.
 */
const carry_order_across_view = (viz_state) => {
  const driver = viz_state.labels.reorder_driver;
  if (driver) {
    const sorted_axis = driver.axis === 'col' ? 'row' : 'col';
    const driver_shown = is_axis_index_visible(
      viz_state,
      driver.axis,
      driver.index
    );
    if (!driver_shown && viz_state.order.current[sorted_axis] === 'custom') {
      viz_state.order.current[sorted_axis] = 'clust';
      viz_state.labels.reorder_driver = null;
    }
  }

  ['row', 'col'].forEach((axis) => sync_order_control(viz_state, axis));
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
  const changed = set_rank_view_state(viz_state, target);

  // Snapping is observable state even when the geometry is already at this
  // stop. Echo it before the early return so Python and the slider converge.
  sync_rank_view_model(viz_state, target);
  viz_state.rank_view?.sync_control?.(target);
  if (!changed) return false;

  // A crop selects matrix row indices, which point at unrelated rows once the
  // level changes — so it resets rather than carrying over. Cropping *within* a
  // view still works; the two filters intersect until the next level switch.
  clear_crop_for_filter_change(deck_mat, layers_mat, viz_state);

  // Geometry changes wholesale here, so mint a fresh body layer rather than
  // letting deck.gl try to tween between two unrelated row sets.
  viz_state.mat._body_layer_rev = (viz_state.mat._body_layer_rev || 0) + 1;

  refresh_rank_view_dendro(viz_state);
  carry_order_across_view(viz_state);
  refresh_filtered_layers(deck_mat, layers_mat, viz_state);
  // Dendrograms show only for CLUST-ordered axes.
  toggle_dendro_layer_visibility(layers_mat, viz_state, 'row');
  toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');

  // Let linked widgets (Enrich, Landscape) drop the gene set the cleared crop
  // had pushed to them.
  sync_gene_row_crop_selection(viz_state);

  // `snap_annotations` is what actually renders here, and it must stay the last
  // setProps: it clones the labels and attribute bars with transitions off so
  // they jump straight to the new layout. Tweening them would be a lie anyway --
  // the matrix cells underneath swap outright rather than animating, since each
  // level is its own independent bi-clustering.
  reset_view_to_filter(deck_mat, layers_mat, viz_state, {
    snap_annotations: true,
  });

  viz_state.crop?.refresh_controls?.();

  return true;
};
