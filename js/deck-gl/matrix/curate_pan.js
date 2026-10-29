import {
  get_axis_slot_size,
  get_default_pan_y,
} from '../../matrix/crop_filter';

export const curate_pan_y = (target_y, zoom_curated_y, viz_state) => {
  const ini_pan_y = get_default_pan_y(viz_state);
  const row_slot = get_axis_slot_size(viz_state, 'row');

  let pan_curated_y;

  const zoom_factor_y = Math.pow(2, zoom_curated_y);

  viz_state.zoom.min_pan_y = (ini_pan_y - row_slot) / zoom_factor_y + row_slot;

  // calculating the shift to the min, to re-use for the max
  const min_diff = ini_pan_y - viz_state.zoom.min_pan_y;

  viz_state.zoom.max_pan_y = ini_pan_y + min_diff;

  if (target_y <= viz_state.zoom.min_pan_y) {
    pan_curated_y = viz_state.zoom.min_pan_y;
  } else if (target_y > viz_state.zoom.max_pan_y) {
    pan_curated_y = viz_state.zoom.max_pan_y;
  } else {
    pan_curated_y = target_y;
  }

  return pan_curated_y;
};

export const curate_pan_x = (target_x, zoom_curated_x, viz_state) => {
  const { ini_pan_x } = viz_state.zoom;

  let pan_curated_x;

  const zoom_factor_x = Math.pow(2, zoom_curated_x);

  viz_state.zoom.min_pan_x = ini_pan_x / zoom_factor_x;

  // calculating the shift to the min, to re-use for the max
  const min_diff = ini_pan_x - viz_state.zoom.min_pan_x;

  viz_state.zoom.max_pan_x = ini_pan_x + min_diff;

  if (target_x <= viz_state.zoom.min_pan_x) {
    pan_curated_x = viz_state.zoom.min_pan_x;
  } else if (target_x > viz_state.zoom.max_pan_x) {
    pan_curated_x = viz_state.zoom.max_pan_x;
  } else {
    pan_curated_x = target_x;
  }

  return pan_curated_x;
};
