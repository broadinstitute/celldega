import { composition_row_label_position } from '../../matrix/composition_data';
import {
  get_axis_center_position,
  get_axis_display_count,
  get_zoomed_axis_label_font_size,
} from '../../matrix/crop_filter';

import { curate_pan_x, curate_pan_y } from './curate_pan';
import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { ini_views } from './views';
import { update_zoom_data } from './zoom';

const MIN_VISIBLE_ROWS = 20;
const ACCORDION_ROW_TO_COL_RATIO = 1.2;

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

  ini_views(viz_state);
  deck_mat.setProps({
    viewState: global_view_state,
    views: viz_state.views.views_list,
    layers: get_mat_layers_list(layers_mat),
  });

  return true;
};
