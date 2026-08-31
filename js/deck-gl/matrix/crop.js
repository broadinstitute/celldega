import { sync_selected_genes } from '../../global_variables/selected_genes';
import {
  refresh_row_label_visibility,
  set_composition_colors,
} from '../../matrix/composition_data';
import {
  clear_crop_display_cache,
  clone_crop_filter,
  get_axis_indices_in_range,
  get_axis_slot_size,
  get_default_pan,
  has_axis_filter,
  has_crop_filter,
  normalize_crop_filter,
} from '../../matrix/crop_filter';
import {
  calc_dendro_polygons,
  calc_dendro_triangles,
} from '../../matrix/dendro';
import { apply_mat_encoding } from '../../matrix/mat_data';
import { refresh_matrix_cat_bars } from '../../ui/matrix_cat_bars';

import {
  ini_row_cat_layer,
  ini_col_cat_layer,
  set_cat_layer_handlers,
} from './cat_layers';
import {
  ini_composition_layer,
  set_composition_layer_onhover,
} from './composition_layer';
import {
  clear_dendro_focus,
  clear_dendro_selection,
  set_dendro_layer_onclick,
  set_dendro_layer_onhover,
  toggle_dendro_layer_visibility,
  update_dendro_layer_data,
} from './dendro_layers';
import {
  ini_row_label_layer,
  ini_col_label_layer,
  refresh_row_label_focus_layer,
  set_col_label_layer_onclick,
  set_col_label_layer_onhover,
  set_row_label_layer_onclick,
  set_row_label_layer_onhover,
} from './label_layers';
import {
  ini_mat_layer,
  set_mat_layer_onclick,
  set_mat_layer_onhover,
} from './mat_layer';
import { get_mat_layers_list } from './matrix_layers';
import { hide_tooltip } from './matrix_tooltip';
import { redefine_global_view_state } from './redefine_global_view_state';
import { ini_views } from './views';
import { update_zoom_data } from './zoom';

const CROP_MIN_DRAG_PX = 8;
const CROP_SNAP_RENDER_WINDOW_MS = 120;
const CROP_AXES = ['row', 'col'];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

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

const empty_dendro_crop_axes = () => ({
  row: null,
  col: null,
});

const empty_crop_filter = () => ({
  row: null,
  col: null,
});

export const sync_gene_row_crop_selection = (viz_state) => {
  const row_entity =
    viz_state.row_entity?.entity ?? viz_state.row_entity ?? null;
  if (String(row_entity).toLowerCase() !== 'gene') return [];

  const row_indices = viz_state.crop?.filter?.row;
  if (!Array.isArray(row_indices) || row_indices.length === 0) {
    // A previously synced gene crop was undone/cleared: propagate the empty
    // selection so linked widgets (Enrich, spatial views) drop the stale crop
    // rather than keep highlighting genes that are no longer cropped.
    if (viz_state.crop?._synced_gene_crop) {
      viz_state.crop._synced_gene_crop = false;
      viz_state.click = {
        type: 'row_crop',
        value: {
          selected_names: [],
          selected_indices: [],
          is_unselecting: true,
          entity: viz_state.row_entity?.entity,
          attr: viz_state.row_entity?.attr,
          row_entity: viz_state.row_entity?.entity,
          row_entity_full: viz_state.row_entity,
        },
      };
      if (viz_state.model?.set) {
        viz_state.model.set('click_info', null);
        viz_state.model.set('click_info', viz_state.click);
      }
      sync_selected_genes(viz_state, []);
    }
    return [];
  }

  const genes = Array.from(
    new Set(
      row_indices
        .map(
          (index) =>
            viz_state.row_nodes?.[index]?.name ||
            viz_state.labels?.row_label_data?.[index]?.name
        )
        .filter(Boolean)
        .map((name) => String(name))
    )
  );
  if (genes.length === 0) return [];

  viz_state.click = {
    type: 'row_crop',
    value: {
      selected_names: genes,
      selected_indices: row_indices.slice(),
      entity: viz_state.row_entity.entity,
      attr: viz_state.row_entity.attr,
      row_entity: viz_state.row_entity.entity,
      row_entity_full: viz_state.row_entity,
    },
  };

  if (viz_state.model?.set) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
  }

  sync_selected_genes(viz_state, genes);
  if (viz_state.crop) {
    viz_state.crop._synced_gene_crop = true;
  }
  return genes;
};

const clone_dendro_crop_source = (source, fallback_indices = null) => {
  if (!source && !fallback_indices) return null;

  return {
    name: source?.name ?? null,
    indices: Array.isArray(source?.indices)
      ? source.indices.slice()
      : Array.isArray(fallback_indices)
        ? fallback_indices.slice()
        : [],
  };
};

const clone_dendro_crop_axes = (dendro_axes) => ({
  row: clone_dendro_crop_source(dendro_axes?.row),
  col: clone_dendro_crop_source(dendro_axes?.col),
});

const clone_crop_state = (viz_state) => ({
  filter: clone_crop_filter(viz_state.crop?.filter),
  dendro_axes: clone_dendro_crop_axes(viz_state.crop?.dendro_axes),
});

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

const refresh_filtered_layers = (deck_mat, layers_mat, viz_state) => {
  clear_crop_display_cache(viz_state);

  viz_state.mat._comp_cache = null;

  if (viz_state.mat.viz_mode === 'composition') {
    set_composition_colors(viz_state);
    layers_mat.mat_layer = ini_composition_layer(viz_state);
    set_mat_layer_onclick(deck_mat, layers_mat, viz_state);
    set_composition_layer_onhover(deck_mat, layers_mat, viz_state);
  } else {
    apply_mat_encoding(viz_state);
    layers_mat.mat_layer = ini_mat_layer(viz_state);
    set_mat_layer_onclick(deck_mat, layers_mat, viz_state);
    set_mat_layer_onhover(deck_mat, layers_mat, viz_state);
  }

  layers_mat.row_label_layer = ini_row_label_layer(viz_state);
  // Rebuild the bold focus overlay against the new crop geometry (the focused
  // row simply drops out of the overlay's data while cropped away).
  refresh_row_label_focus_layer(layers_mat, viz_state);
  layers_mat.col_label_layer = ini_col_label_layer(viz_state);
  layers_mat.row_cat_layer = ini_row_cat_layer(viz_state);
  layers_mat.col_cat_layer = ini_col_cat_layer(viz_state);

  set_row_label_layer_onclick(deck_mat, layers_mat, viz_state);
  set_col_label_layer_onclick(deck_mat, layers_mat, viz_state);
  set_row_label_layer_onhover(deck_mat, layers_mat, viz_state);
  set_col_label_layer_onhover(deck_mat, layers_mat, viz_state);
  set_cat_layer_handlers(deck_mat, layers_mat, viz_state, 'row');
  set_cat_layer_handlers(deck_mat, layers_mat, viz_state, 'col');

  ['row', 'col'].forEach((axis) => {
    calc_dendro_triangles(viz_state, axis);
    calc_dendro_polygons(viz_state, axis);
    update_dendro_layer_data(layers_mat, viz_state, axis);
    set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, axis);
    set_dendro_layer_onhover(deck_mat, layers_mat, viz_state, axis);
    toggle_dendro_layer_visibility(layers_mat, viz_state, axis);
  });

  if (viz_state.mat.viz_mode === 'composition') {
    layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
      visible: false,
    });
  } else {
    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
      visible: true,
    });
    layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
      visible: true,
    });
  }

  refresh_row_label_visibility(layers_mat, viz_state);
  refresh_matrix_cat_bars(viz_state);
};

const enable_crop_annotation_snap = (viz_state) => {
  if (!viz_state.crop) return;

  clearTimeout(viz_state.crop._snap_timer);
  viz_state.crop._snap_annotation_transitions = true;
  viz_state.crop._snap_timer = setTimeout(() => {
    viz_state.crop._snap_annotation_transitions = false;
    viz_state.crop._snap_timer = null;
  }, CROP_SNAP_RENDER_WINDOW_MS);
};

const reset_view_to_filter = (
  deck_mat,
  layers_mat,
  viz_state,
  options = {}
) => {
  const { snap_annotations = false } = options;
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
  if (snap_annotations) {
    enable_crop_annotation_snap(viz_state);
  }

  deck_mat.setProps({
    viewState: global_view_state,
    views: viz_state.views.views_list,
    layers: get_mat_layers_list(layers_mat, { snap_annotations }),
  });
};

const refresh_dendro_sliders = (viz_state) => {
  CROP_AXES.forEach((axis) => {
    const slider = viz_state.dendro?.sliders?.[axis];
    if (!slider) return;

    const disabled = has_axis_filter(viz_state, axis);
    slider.disabled = disabled;
    slider.style.opacity = disabled ? '0.35' : '1';
    slider.style.cursor = disabled ? 'not-allowed' : '';
    slider.title = disabled
      ? `Undo the ${axis} crop before changing this dendrogram slice.`
      : '';
  });
};

const refresh_controls = (viz_state) => {
  refresh_dendro_sliders(viz_state);

  if (!viz_state.crop?.controls) return;

  const can_crop = !has_crop_filter(viz_state) && !viz_state.crop.fade_filter;

  viz_state.crop.controls.set_active(viz_state.crop.active && can_crop);
  viz_state.crop.controls.set_crop_enabled?.(can_crop);
  viz_state.crop.controls.set_undo_enabled(has_crop_filter(viz_state));
};

const apply_crop_filter = (
  deck_mat,
  layers_mat,
  viz_state,
  filter,
  options = {}
) => {
  clear_crop_fade(viz_state);
  viz_state.crop.filter = normalize_crop_filter(viz_state, filter);
  viz_state.crop.dendro_axes = clone_dendro_crop_axes(options.dendro_axes);
  viz_state.mat._body_layer_rev = (viz_state.mat._body_layer_rev || 0) + 1;
  clear_crop_display_cache(viz_state);
  clear_crop_interaction_state(deck_mat, layers_mat, viz_state);
  refresh_filtered_layers(deck_mat, layers_mat, viz_state);
  sync_gene_row_crop_selection(viz_state);

  reset_view_to_filter(deck_mat, layers_mat, viz_state, {
    snap_annotations: true,
  });
  refresh_controls(viz_state);
};

const clear_all_crops = (deck_mat, layers_mat, viz_state) => {
  const current_filter = normalize_crop_filter(
    viz_state,
    viz_state.crop.filter
  );

  if (!has_crop_filter(viz_state) && viz_state.crop.history.length === 0) {
    return false;
  }

  viz_state.crop.history = [];
  viz_state.crop.set_mode(false);
  apply_crop_filter(deck_mat, layers_mat, viz_state, empty_crop_filter(), {
    dendro_axes: empty_dendro_crop_axes(),
  });

  return !filters_equal(current_filter, empty_crop_filter());
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
    dendro_axes: clone_dendro_crop_axes(existing_crop.dendro_axes),
    fade_filter: null,
    _fade_rev: existing_crop._fade_rev || 0,
    _fade_timer: null,
    _snap_annotation_transitions: false,
    _snap_timer: null,
    controls: null,
    overlay,
    on_mode_change: options.on_mode_change || null,
    refresh_controls: () => refresh_controls(viz_state),
    apply_filter: (filter, apply_options = {}) => {
      const { push_history = true, dendro_axes = empty_dendro_crop_axes() } =
        apply_options;
      const current_filter = normalize_crop_filter(
        viz_state,
        viz_state.crop.filter
      );
      const next_filter = normalize_crop_filter(viz_state, filter);

      if (filters_equal(current_filter, next_filter)) {
        return false;
      }

      if (push_history && viz_state.crop.history.length === 0) {
        viz_state.crop.history.push(clone_crop_state(viz_state));
      }

      viz_state.crop.set_mode(false);
      apply_crop_filter(deck_mat, layers_mat, viz_state, next_filter, {
        dendro_axes,
      });
      return true;
    },
    apply_axis_crop: (axis, indices, crop_options = {}) => {
      if (axis !== 'row' && axis !== 'col') {
        return false;
      }

      const current_filter = normalize_crop_filter(
        viz_state,
        viz_state.crop.filter
      );
      const next_filter = clone_crop_filter(current_filter);
      const next_dendro_axes = clone_dendro_crop_axes(
        viz_state.crop.dendro_axes
      );

      if (current_filter[axis]) {
        return clear_all_crops(deck_mat, layers_mat, viz_state);
      }

      next_filter[axis] = Array.isArray(indices) ? indices.slice() : null;
      next_dendro_axes[axis] = clone_dendro_crop_source(
        crop_options.source,
        indices
      );

      return viz_state.crop.apply_filter(next_filter, {
        push_history: true,
        dendro_axes: next_dendro_axes,
      });
    },
    set_controls: (controls) => {
      viz_state.crop.controls = controls;
      refresh_controls(viz_state);
    },
    set_mode: (active) => {
      if (
        active &&
        (has_crop_filter(viz_state) || viz_state.crop.fade_filter)
      ) {
        active = false;
      }

      viz_state.crop.active = active;
      viz_state.crop.drag = null;
      hide_overlay(overlay);
      viz_state.crop.on_mode_change?.(active);
      refresh_controls(viz_state);
    },
    toggle: () => {
      if (has_crop_filter(viz_state)) {
        viz_state.crop.set_mode(false);
        return;
      }

      viz_state.crop.set_mode(!viz_state.crop.active);
    },
    undo: () => {
      clear_all_crops(deck_mat, layers_mat, viz_state);
    },
    on_drag_start: (info) => {
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

      hide_tooltip(viz_state);
      set_overlay_bounds(overlay, start_screen, start_screen);
    },
    on_drag: (info) => {
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
    on_drag_end: (info) => {
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

      // apply_filter normalizes and no-ops on an unchanged filter itself.
      viz_state.crop.apply_filter(raw_filter, { push_history: true });
    },
  };
};
