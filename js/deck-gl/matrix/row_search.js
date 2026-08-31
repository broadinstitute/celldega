import * as d3 from 'd3';
import { LinearInterpolator } from 'deck.gl';

import { composition_row_label_position } from '../../matrix/composition_data';
import {
  get_axis_center_position,
  get_axis_display_count,
  get_zoomed_axis_label_font_size,
} from '../../matrix/crop_filter';

import { curate_pan_x, curate_pan_y } from './curate_pan';
import { refresh_row_label_focus_layer } from './label_layers';
import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { ini_views } from './views';
import { update_zoom_data } from './zoom';

const MIN_VISIBLE_ROWS = 20;
const ACCORDION_ROW_TO_COL_RATIO = 1.2;
// View-state fly-to duration for focusing a row (search bar or an Enrich gene
// click). Deliberately quicker than viz_state.animate.duration (the 2.5s
// reorder animation) — this is navigation, not a data morph.
export const FOCUS_ZOOM_TRANSITION_MS = 750;

/**
 * Decorate every view's state with the same zoom/pan transition so the
 * matrix, label, and dendrogram viewports fly to the focused row in sync.
 * Static views transition between identical states, which is a no-op.
 */
export const with_focus_zoom_transitions = (
  view_state_map,
  duration = FOCUS_ZOOM_TRANSITION_MS
) => {
  const animated = {};
  Object.entries(view_state_map).forEach(([view_id, view_state]) => {
    animated[view_id] = {
      ...view_state,
      transitionDuration: duration,
      transitionInterpolator: new LinearInterpolator({
        transitionProps: ['target', 'zoom'],
      }),
      transitionEasing: d3.easeCubic,
    };
  });
  return animated;
};

/**
 * Mark the window in which deck.gl emits per-frame onViewStateChange events
 * for a transition we initiated. on_view_state_change must ignore those
 * frames: the zoom bookkeeping was already set to the transition's final
 * values, and re-deriving state from interpolated frames would both corrupt
 * it and cancel the animation.
 */
const mark_programmatic_view_transition = (viz_state, duration) => {
  clearTimeout(viz_state.zoom._programmatic_transition_timer);
  viz_state.zoom._programmatic_view_transition = true;
  viz_state.zoom._programmatic_transition_timer = setTimeout(() => {
    viz_state.zoom._programmatic_view_transition = false;
    viz_state.zoom._programmatic_transition_timer = null;
  }, duration + 150);
};

export const get_row_search_zoom = (viz_state, current_zoom) => {
  const row_count = get_axis_display_count(viz_state, 'row');
  const col_count = get_axis_display_count(viz_state, 'col');
  const [current_x, current_y] = current_zoom;

  // Search remains useful for wide matrices (it can pan to an already visible
  // row), but only the vertical accordion gets an automatic magnification.
  if (row_count <= col_count || viz_state.mat.viz_mode === 'composition') {
    return [current_x, current_y];
  }

  // Keep roughly one column-width of rows visible. The small buffer leaves
  // the controller in vertical accordion mode rather than unlocking X zoom.
  const visible_rows = Math.max(
    MIN_VISIBLE_ROWS,
    col_count * ACCORDION_ROW_TO_COL_RATIO
  );
  const target_y = Math.max(0, Math.log2(row_count / visible_rows));
  const zoom_y = Math.max(current_y, target_y);
  const zoom_x = Math.max(
    current_x,
    viz_state.zoom.ini_zoom_x,
    zoom_y - viz_state.zoom.zoom_delay
  );

  return [zoom_x, zoom_y];
};

export const focus_matrix_row = (
  deck_mat,
  layers_mat,
  viz_state,
  row_index
) => {
  // Composition mode lays rows out as stacked bar segments, not uniform grid
  // slots, so the pan target must come from the composition layout.
  const row_center =
    viz_state.mat.viz_mode === 'composition'
      ? composition_row_label_position(viz_state, row_index)[1]
      : get_axis_center_position(viz_state, 'row', row_index);
  if (row_center === null) return false;

  const current_zoom = [
    viz_state.zoom.zoom_data.matrix.zoom_x,
    viz_state.zoom.zoom_data.matrix.zoom_y,
  ];
  const current_pan = [
    viz_state.zoom.zoom_data.matrix.pan_x,
    viz_state.zoom.zoom_data.matrix.pan_y,
  ];
  const zoom_curated = get_row_search_zoom(viz_state, current_zoom);
  const pan_curated = [
    curate_pan_x(current_pan[0], zoom_curated[0], viz_state),
    curate_pan_y(row_center, zoom_curated[1], viz_state),
  ];
  const global_view_state = redefine_global_view_state(
    viz_state,
    'matrix',
    zoom_curated,
    pan_curated
  );

  update_zoom_data(viz_state, 'matrix', zoom_curated, pan_curated);
  viz_state.zoom.zoom_data.total_zoom.x = zoom_curated[0];
  viz_state.zoom.zoom_data.total_zoom.y = zoom_curated[1];

  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    getSize: get_zoomed_axis_label_font_size(viz_state, 'row', zoom_curated[1]),
  });
  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    getSize: get_zoomed_axis_label_font_size(viz_state, 'col', zoom_curated[0]),
  });

  // Bold the focused row's label (one-datum overlay drawn over the base
  // label), sized like the base labels at the destination zoom.
  viz_state.labels.focused_row_index = row_index;
  refresh_row_label_focus_layer(layers_mat, viz_state);

  ini_views(viz_state);
  mark_programmatic_view_transition(viz_state, FOCUS_ZOOM_TRANSITION_MS);
  deck_mat.setProps({
    viewState: with_focus_zoom_transitions(global_view_state),
    views: viz_state.views.views_list,
    layers: get_mat_layers_list(layers_mat),
  });

  return true;
};
