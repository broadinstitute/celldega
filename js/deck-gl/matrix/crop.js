import { refresh_row_label_visibility } from '../../matrix/composition_data';
import {
  clear_crop_display_cache,
  clone_crop_filter,
  crop_fade_signature,
  crop_filter_signature,
  filter_cat_data,
  filter_label_data,
  filter_matrix_data,
  get_axis_indices_in_range,
  get_axis_label_font_size,
  get_axis_slot_size,
  get_default_pan,
  has_crop_filter,
  normalize_crop_filter,
} from '../../matrix/crop_filter';
import {
  calc_dendro_polygons,
  calc_dendro_triangles,
} from '../../matrix/dendro';
import { refresh_matrix_cat_bars } from '../../ui/matrix_cat_bars';

import {
  clear_dendro_focus,
  clear_dendro_selection,
  update_dendro_layer_data,
} from './dendro_layers';
import { get_mat_layers_list, mat_reorder_triggers } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { ini_views } from './views';
import { update_zoom_data } from './zoom';

const CROP_MIN_DRAG_PX = 8;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const get_layer_update_triggers = (layer) => layer?.props?.updateTriggers || {};

const get_matrix_screen_bounds = (viz_state) => {
  const left = viz_state.viz.row_region + viz_state.viz.label_buffer;
  const top = viz_state.viz.col_region + viz_state.viz.label_buffer;

  return {
    left,
    top,
    right: left + viz_state.viz.mat_width,
    bottom: top + viz_state.viz.mat_height,
  };
};

const get_matrix_world_bounds = (viz_state) => {
  const row_slot = get_axis_slot_size(viz_state, 'row');

  return {
    min_x: 0,
    max_x: viz_state.viz.mat_width,
    min_y: row_slot,
    max_y: viz_state.viz.mat_height + row_slot,
  };
};

const clamp_screen_point = (viz_state, x, y) => {
  const bounds = get_matrix_screen_bounds(viz_state);

  return [
    clamp(x, bounds.left, bounds.right),
    clamp(y, bounds.top, bounds.bottom),
  ];
};

const clamp_world_point = (viz_state, coord) => {
  const bounds = get_matrix_world_bounds(viz_state);

  return [
    clamp(coord[0], bounds.min_x, bounds.max_x),
    clamp(coord[1], bounds.min_y, bounds.max_y),
  ];
};

const get_matrix_viewport = (deck_mat) =>
  deck_mat.viewManager
    ?.getViewports()
    ?.find((viewport) => viewport.id === 'matrix');

const screen_to_matrix_world = (deck_mat, viz_state, x, y) => {
  const viewport = get_matrix_viewport(deck_mat);
  if (!viewport) return null;

  const [clamped_x, clamped_y] = clamp_screen_point(viz_state, x, y);
  const coordinate = viewport.unproject([
    clamped_x - viewport.x,
    clamped_y - viewport.y,
  ]);

  return Array.isArray(coordinate)
    ? clamp_world_point(viz_state, coordinate)
    : null;
};

const set_overlay_bounds = (overlay, start_screen, end_screen) => {
  const left = Math.min(start_screen[0], end_screen[0]);
  const top = Math.min(start_screen[1], end_screen[1]);
  const width = Math.abs(end_screen[0] - start_screen[0]);
  const height = Math.abs(end_screen[1] - start_screen[1]);

  overlay.style.display = 'block';
  overlay.style.left = `${left}px`;
  overlay.style.top = `${top}px`;
  overlay.style.width = `${width}px`;
  overlay.style.height = `${height}px`;
};

const hide_overlay = (overlay) => {
  overlay.style.display = 'none';
  overlay.style.width = '0px';
  overlay.style.height = '0px';
};

const filters_equal = (a, b) =>
  JSON.stringify(a || { row: null, col: null }) ===
  JSON.stringify(b || { row: null, col: null });

const clear_crop_fade = (viz_state) => {
  if (!viz_state.crop) return;

  clearTimeout(viz_state.crop._fade_timer);
  viz_state.crop._fade_timer = null;

  if (viz_state.crop.fade_filter) {
    viz_state.crop.fade_filter = null;
    viz_state.crop._fade_rev = (viz_state.crop._fade_rev || 0) + 1;
  }
};

const clear_crop_interaction_state = (deck_mat, layers_mat, viz_state) => {
  clearTimeout(viz_state.dendro?._hover_timer);
  if (viz_state.dendro) {
    viz_state.dendro._hover_target = null;
    viz_state.dendro.highlight = { row: null, col: null };
    viz_state.dendro._highlight_rev =
      (viz_state.dendro._highlight_rev || 0) + 1;
  }

  clearTimeout(viz_state.mat?._comp_hover_timer);
  clearTimeout(viz_state.mat?._comp_hover_col_timer);
  viz_state.mat.comp_hover_row = null;
  viz_state.mat.comp_hover_col = null;

  viz_state.hovered_cat = null;
  viz_state.obs_store?.hovered_category?.set(null);
  viz_state.obs_store?.dendro_selection?.set(null);
  viz_state.obs_store?.category_breakdown?.set({ row: {}, col: {} });

  clear_dendro_selection(deck_mat, layers_mat, viz_state, { render: false });
  clear_dendro_focus(deck_mat, layers_mat, viz_state, { render: false });
};

const mat_fill_trigger = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  const fade_sig = crop_fade_signature(viz_state);

  if (viz_state.mat.viz_mode === 'composition') {
    return [
      viz_state.mat.viz_mode,
      viz_state.mat.comp_hover_row,
      viz_state.mat.comp_hover_col,
      crop_sig,
      fade_sig,
      viz_state.dendro?._highlight_rev || 0,
    ];
  }

  return [crop_sig, fade_sig, viz_state.dendro?._highlight_rev || 0];
};

const cat_fill_trigger = (viz_state) => [
  crop_filter_signature(viz_state),
  crop_fade_signature(viz_state),
  viz_state.hovered_cat,
];

const row_label_color_trigger = (viz_state) => [
  crop_filter_signature(viz_state),
  crop_fade_signature(viz_state),
  viz_state.labels._row_vis_rev || 0,
];

const col_label_color_trigger = (viz_state) => [
  crop_filter_signature(viz_state),
  crop_fade_signature(viz_state),
];

const refresh_filtered_layers = (layers_mat, viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  clear_crop_display_cache(viz_state);

  viz_state.mat._comp_cache = null;

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    data: filter_matrix_data(viz_state),
    tile_height: get_axis_slot_size(viz_state, 'row') * 0.5,
    tile_width: get_axis_slot_size(viz_state, 'col') * 0.5,
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.mat_layer),
      ...mat_reorder_triggers(viz_state),
      getFillColor: mat_fill_trigger(viz_state),
    },
  });

  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    data: filter_label_data(viz_state, 'row'),
    getSize: get_axis_label_font_size(viz_state, 'row'),
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.row_label_layer),
      getPosition: [viz_state.order.current.row, crop_sig],
      getColor: row_label_color_trigger(viz_state),
      getSize: crop_sig,
    },
  });

  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    data: filter_label_data(viz_state, 'col'),
    getSize: get_axis_label_font_size(viz_state, 'col'),
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.col_label_layer),
      getPosition: [viz_state.order.current.col, crop_sig],
      getPixelOffset: [crop_sig, viz_state.zoom.zoom_data.matrix.zoom_x],
      getColor: col_label_color_trigger(viz_state),
      getSize: crop_sig,
    },
  });

  layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
    data: filter_cat_data(viz_state, 'row'),
    tile_height: get_axis_slot_size(viz_state, 'row') * 0.5,
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.row_cat_layer),
      getPosition: [viz_state.order.current.row, crop_sig],
      getFillColor: cat_fill_trigger(viz_state),
    },
  });

  layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
    data: filter_cat_data(viz_state, 'col'),
    tile_width: get_axis_slot_size(viz_state, 'col') * 0.5,
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.col_cat_layer),
      getPosition: [viz_state.order.current.col, crop_sig],
      getFillColor: cat_fill_trigger(viz_state),
    },
  });

  ['row', 'col'].forEach((axis) => {
    calc_dendro_triangles(viz_state, axis);
    calc_dendro_polygons(viz_state, axis);
    update_dendro_layer_data(layers_mat, viz_state, axis);
  });

  refresh_row_label_visibility(layers_mat, viz_state);
  refresh_matrix_cat_bars(viz_state);
};

const reset_view_to_filter = (deck_mat, layers_mat, viz_state) => {
  const zoom_curated = [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y];
  const pan_curated = get_default_pan(viz_state);
  const global_view_state = redefine_global_view_state(
    viz_state,
    'matrix',
    zoom_curated,
    pan_curated
  );

  update_zoom_data(viz_state, 'matrix', zoom_curated, pan_curated);
  viz_state.zoom.zoom_data.total_zoom.x = zoom_curated[0];
  viz_state.zoom.zoom_data.total_zoom.y = zoom_curated[1];
  ini_views(viz_state);

  deck_mat.setProps({
    viewState: global_view_state,
    views: viz_state.views.views_list,
    layers: get_mat_layers_list(layers_mat),
  });
};

const refresh_controls = (viz_state) => {
  if (!viz_state.crop?.controls) return;

  const can_crop = !has_crop_filter(viz_state) && !viz_state.crop.fade_filter;

  viz_state.crop.controls.setActive(viz_state.crop.active && can_crop);
  viz_state.crop.controls.setCropEnabled?.(can_crop);
  viz_state.crop.controls.setUndoEnabled(viz_state.crop.history.length > 0);
};

const apply_crop_filter = (deck_mat, layers_mat, viz_state, filter) => {
  clear_crop_fade(viz_state);
  viz_state.crop.filter = normalize_crop_filter(viz_state, filter);
  clear_crop_display_cache(viz_state);
  clear_crop_interaction_state(deck_mat, layers_mat, viz_state);
  refresh_filtered_layers(layers_mat, viz_state);

  [
    'mat_layer',
    'row_label_layer',
    'col_label_layer',
    'row_cat_layer',
    'col_cat_layer',
  ].forEach((layer_key) => {
    if (!layers_mat[layer_key]) return;
    layers_mat[layer_key] = layers_mat[layer_key].clone({
      transitions: false,
    });
  });

  reset_view_to_filter(deck_mat, layers_mat, viz_state);
  refresh_controls(viz_state);
};

export const compute_crop_filter = (viz_state, start_coord, end_coord) => {
  const [start_x, start_y] = clamp_world_point(viz_state, start_coord);
  const [end_x, end_y] = clamp_world_point(viz_state, end_coord);

  return {
    row: get_axis_indices_in_range(viz_state, 'row', start_y, end_y),
    col: get_axis_indices_in_range(viz_state, 'col', start_x, end_x),
  };
};

export const initialize_matrix_crop = (
  deck_mat,
  layers_mat,
  viz_state,
  options = {}
) => {
  viz_state.root.style.position = 'relative';

  const overlay = document.createElement('div');
  overlay.style.position = 'absolute';
  overlay.style.display = 'none';
  overlay.style.pointerEvents = 'none';
  overlay.style.border = '1px solid rgba(56, 109, 241, 0.95)';
  overlay.style.background = 'rgba(56, 109, 241, 0.12)';
  overlay.style.boxSizing = 'border-box';
  overlay.style.zIndex = '2';
  viz_state.root.appendChild(overlay);

  const existing_crop = viz_state.crop || {};

  viz_state.crop = {
    ...existing_crop,
    active: false,
    drag: null,
    filter: normalize_crop_filter(viz_state, existing_crop.filter),
    history: [],
    fade_filter: null,
    _fade_rev: existing_crop._fade_rev || 0,
    _fade_timer: null,
    controls: null,
    overlay,
    onModeChange: options.onModeChange || null,
    refreshControls: () => refresh_controls(viz_state),
    setControls: (controls) => {
      viz_state.crop.controls = controls;
      refresh_controls(viz_state);
    },
    setMode: (active) => {
      if (
        active &&
        (has_crop_filter(viz_state) || viz_state.crop.fade_filter)
      ) {
        active = false;
      }

      viz_state.crop.active = active;
      viz_state.crop.drag = null;
      hide_overlay(overlay);
      viz_state.crop.onModeChange?.(active);
      refresh_controls(viz_state);
    },
    toggle: () => {
      if (has_crop_filter(viz_state)) {
        viz_state.crop.setMode(false);
        return;
      }

      viz_state.crop.setMode(!viz_state.crop.active);
    },
    undo: () => {
      const previous = viz_state.crop.history.pop();
      if (!previous) return;

      clear_crop_fade(viz_state);
      viz_state.crop.setMode(false);
      apply_crop_filter(deck_mat, layers_mat, viz_state, previous);
    },
    onDragStart: (info) => {
      if (
        !viz_state.crop.active ||
        has_crop_filter(viz_state) ||
        info.viewport?.id !== 'matrix'
      )
        return;

      const start_screen = clamp_screen_point(viz_state, info.x, info.y);
      const start_coord = screen_to_matrix_world(
        deck_mat,
        viz_state,
        info.x,
        info.y
      );

      if (!start_coord) return;

      viz_state.crop.drag = {
        start_screen,
        end_screen: start_screen,
        start_coord,
        end_coord: start_coord,
      };

      set_overlay_bounds(overlay, start_screen, start_screen);
    },
    onDrag: (info) => {
      if (!viz_state.crop.drag) return;

      const end_screen = clamp_screen_point(viz_state, info.x, info.y);
      const end_coord = screen_to_matrix_world(
        deck_mat,
        viz_state,
        info.x,
        info.y
      );

      if (!end_coord) return;

      viz_state.crop.drag.end_screen = end_screen;
      viz_state.crop.drag.end_coord = end_coord;

      set_overlay_bounds(
        overlay,
        viz_state.crop.drag.start_screen,
        viz_state.crop.drag.end_screen
      );
    },
    onDragEnd: (info) => {
      if (!viz_state.crop.drag) return;

      if (info?.x != null && info?.y != null) {
        const end_screen = clamp_screen_point(viz_state, info.x, info.y);
        const end_coord = screen_to_matrix_world(
          deck_mat,
          viz_state,
          info.x,
          info.y
        );

        if (end_coord) {
          viz_state.crop.drag.end_screen = end_screen;
          viz_state.crop.drag.end_coord = end_coord;
        }
      }

      const { start_screen, end_screen, start_coord, end_coord } =
        viz_state.crop.drag;

      viz_state.crop.drag = null;
      hide_overlay(overlay);

      const width = Math.abs(end_screen[0] - start_screen[0]);
      const height = Math.abs(end_screen[1] - start_screen[1]);

      if (width < CROP_MIN_DRAG_PX || height < CROP_MIN_DRAG_PX) {
        return;
      }

      const raw_filter = compute_crop_filter(viz_state, start_coord, end_coord);
      if (raw_filter.row.length === 0 || raw_filter.col.length === 0) {
        return;
      }

      const current_filter = normalize_crop_filter(
        viz_state,
        viz_state.crop.filter
      );
      const next_filter = normalize_crop_filter(viz_state, raw_filter);

      if (filters_equal(current_filter, next_filter)) {
        return;
      }

      viz_state.crop.history.push(clone_crop_filter(current_filter));
      viz_state.crop.setMode(false);
      apply_crop_filter(deck_mat, layers_mat, viz_state, next_filter);
    },
  };
};
