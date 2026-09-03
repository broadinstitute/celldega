import * as d3 from 'd3';
import { PolygonLayer } from 'deck.gl';

import {
  sync_selected_genes,
  sync_selected_rows,
  sync_selected_cols,
} from '../../global_variables/selected_genes';
import {
  crop_fade_signature,
  crop_filter_signature,
} from '../../matrix/crop_filter';
import {
  calc_dendro_triangles,
  calc_dendro_polygons,
} from '../../matrix/dendro';

import {
  get_layer_update_triggers,
  get_mat_layers_list,
} from './matrix_layers';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const SELECTED_FILL_COLOR = [0, 0, 0, 135];
const FOCUSED_FILL_COLOR = [0, 0, 0, 180];
const CROPPED_FILL_COLOR = [0, 0, 0, 235];
const DOUBLE_CLICK_DELAY = 350;
const DENDRO_HIGHLIGHT_DIM_ALPHA = 0.04;
const DENDRO_HOVER_DELAY_MS = 60;
const DENDRO_CLICK_VIEWPORT_TOLERANCE = 16;

const ensure_click_tracking = (viz_state) => {
  if (!viz_state.dendro.click_timeouts) {
    viz_state.dendro.click_timeouts = { row: null, col: null };
  }

  if (!viz_state.dendro.pending_click) {
    viz_state.dendro.pending_click = { row: null, col: null };
  }
};

const ensure_selection_tracking = (viz_state) => {
  if (!viz_state.dendro.selected_polygon) {
    viz_state.dendro.selected_polygon = { row: null, col: null };
  }

  return viz_state.dendro.selected_polygon;
};

const clear_pending_axis_click = (viz_state, axis) => {
  ensure_click_tracking(viz_state);
  clearTimeout(viz_state.dendro.click_timeouts[axis]);
  viz_state.dendro.click_timeouts[axis] = null;
  viz_state.dendro.pending_click[axis] = null;
};

const polygon_props_from_pick_info = (info) => {
  if (!info?.object?.properties) return null;

  return {
    ...info.object.properties,
    all_names: [...(info.object.properties.all_names || [])],
    all_indices: [...(info.object.properties.all_indices || [])],
  };
};

const point_in_viewport = (viewport, x, y) =>
  x >= viewport.x - DENDRO_CLICK_VIEWPORT_TOLERANCE &&
  x <= viewport.x + viewport.width + DENDRO_CLICK_VIEWPORT_TOLERANCE &&
  y >= viewport.y - DENDRO_CLICK_VIEWPORT_TOLERANCE &&
  y <= viewport.y + viewport.height + DENDRO_CLICK_VIEWPORT_TOLERANCE;

const dendro_axis_is_interactive = (layers_mat, viz_state, axis) => {
  const layer = layers_mat?.[`${axis}_dendro_layer`];
  const order = viz_state.order?.current?.[axis];
  return (
    layer?.props?.visible !== false && (order == null || order === 'clust')
  );
};

const manual_pick_dendro_polygon = (deck_mat, layers_mat, viz_state, x, y) => {
  const viewports = deck_mat.viewManager?.getViewports?.() || [];

  for (const axis of DENDRO_AXES) {
    if (!dendro_axis_is_interactive(layers_mat, viz_state, axis)) continue;

    const viewport_id = axis === 'row' ? 'dendro_rows' : 'dendro_cols';
    const viewport = viewports.find(
      (inst_viewport) => inst_viewport.id === viewport_id
    );
    if (!viewport || typeof viewport.unproject !== 'function') continue;
    if (!point_in_viewport(viewport, x, y)) continue;

    const point = viewport.unproject([x - viewport.x, y - viewport.y]);
    if (!Array.isArray(point)) continue;

    const polygon = viz_state.dendro.polygons?.[axis]?.find((candidate) =>
      d3.polygonContains(candidate.coordinates, point)
    );
    if (polygon) {
      return {
        axis,
        polygon_props: polygon_props_from_pick_info({ object: polygon }),
      };
    }
  }

  return { axis: null, polygon_props: null };
};

const normalize_focus_map = (raw_focus) => {
  if (!raw_focus) {
    return { row: null, col: null };
  }

  if (
    Object.prototype.hasOwnProperty.call(raw_focus, 'row') ||
    Object.prototype.hasOwnProperty.call(raw_focus, 'col')
  ) {
    return {
      row: raw_focus.row || null,
      col: raw_focus.col || null,
    };
  }

  if (raw_focus.axis && raw_focus.name) {
    return {
      row: raw_focus.axis === 'row' ? raw_focus : null,
      col: raw_focus.axis === 'col' ? raw_focus : null,
    };
  }

  return { row: null, col: null };
};

const get_current_focus_map = (viz_state) => {
  const store_focus =
    viz_state?.obs_store?.focused_dendro &&
    typeof viz_state.obs_store.focused_dendro.get === 'function'
      ? viz_state.obs_store.focused_dendro.get()
      : null;

  return normalize_focus_map(
    store_focus ?? viz_state.dendro?.active_polygon ?? null
  );
};

const get_axis_focus = (viz_state, axis) =>
  get_current_focus_map(viz_state)[axis];

const get_polygon_by_name = (viz_state, axis, polygon_name) =>
  viz_state.dendro.polygons?.[axis]?.find(
    (polygon) => polygon.properties.name === polygon_name
  );

const sorted_number_key = (values) =>
  Array.isArray(values)
    ? values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value))
        .sort((a, b) => a - b)
        .join(',')
    : '';

const is_dendro_crop_source = (viz_state, axis, polygon) => {
  const source = viz_state.crop?.dendro_axes?.[axis];
  const axis_filter = viz_state.crop?.filter?.[axis];
  if (!source || !Array.isArray(axis_filter)) return false;

  if (source.name != null && polygon.properties.name === source.name) {
    return true;
  }

  return (
    sorted_number_key(source.indices || axis_filter) ===
    sorted_number_key(polygon.properties.all_indices)
  );
};

export const clear_dendro_focus = (
  deck_mat,
  layers_mat,
  viz_state,
  options = {}
) => {
  const { clearHighlight = true, render = true } = options;
  const focus = get_current_focus_map(viz_state);

  ensure_click_tracking(viz_state);
  DENDRO_AXES.forEach((axis) => {
    clear_pending_axis_click(viz_state, axis);
  });

  if (!focus.row && !focus.col) {
    return false;
  }

  viz_state.dendro.active_polygon = { row: null, col: null };

  if (viz_state.obs_store?.focused_dendro) {
    viz_state.obs_store.focused_dendro.set(viz_state.dendro.active_polygon);
  }

  DENDRO_AXES.forEach((axis) => {
    const polygons = viz_state.dendro.polygons?.[axis];
    if (!polygons) return;

    const updated_polygons = polygons.map((polygon) =>
      polygon.properties.is_focused
        ? {
            ...polygon,
            properties: {
              ...polygon.properties,
              is_focused: false,
            },
          }
        : polygon
    );

    viz_state.dendro.polygons[axis] = updated_polygons;

    if (layers_mat[`${axis}_dendro_layer`]) {
      layers_mat[`${axis}_dendro_layer`] = layers_mat[
        `${axis}_dendro_layer`
      ].clone({
        data: updated_polygons,
      });
    }
  });

  if (clearHighlight) {
    viz_state.dendro.highlight = { row: null, col: null };
    viz_state.dendro._highlight_rev =
      (viz_state.dendro._highlight_rev || 0) + 1;

    if (layers_mat.mat_layer) {
      layers_mat.mat_layer = layers_mat.mat_layer.clone({
        updateTriggers: {
          ...get_layer_update_triggers(layers_mat.mat_layer),
          getFillColor: [
            crop_filter_signature(viz_state),
            crop_fade_signature(viz_state),
            viz_state.mat?.comp_hover_row,
            viz_state.mat?.comp_hover_col,
            viz_state.dendro._highlight_rev,
          ],
        },
      });
    }
  }

  if (render && typeof deck_mat?.setProps === 'function') {
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }

  return true;
};

export const clear_dendro_selection = (
  deck_mat,
  layers_mat,
  viz_state,
  options = {}
) => {
  const { render = true } = options;
  ensure_selection_tracking(viz_state);

  viz_state.dendro.selected_polygon = { row: null, col: null };

  let did_update = false;
  DENDRO_AXES.forEach((axis) => {
    const polygons = viz_state.dendro.polygons?.[axis];
    if (!polygons) return;

    const updated_polygons = polygons.map((polygon) => {
      if (!polygon.properties.is_selected) return polygon;
      did_update = true;
      return {
        ...polygon,
        properties: {
          ...polygon.properties,
          is_selected: false,
        },
      };
    });

    viz_state.dendro.polygons[axis] = updated_polygons;

    if (layers_mat[`${axis}_dendro_layer`]) {
      layers_mat[`${axis}_dendro_layer`] = layers_mat[
        `${axis}_dendro_layer`
      ].clone({
        data: updated_polygons,
      });
    }
  });

  if (did_update && render && typeof deck_mat?.setProps === 'function') {
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }

  return did_update;
};

const apply_dendro_selection_visual = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_name
) => {
  const next_selection = { row: null, col: null };
  if (axis && polygon_name) {
    next_selection[axis] = { axis, name: polygon_name };
  }
  viz_state.dendro.selected_polygon = next_selection;

  let did_update = false;
  DENDRO_AXES.forEach((target_axis) => {
    const polygons = viz_state.dendro.polygons?.[target_axis];
    if (!polygons) return;

    const selected_name = next_selection[target_axis]?.name || null;
    const updated_polygons = polygons.map((polygon) => {
      const is_selected = polygon.properties.name === selected_name;
      if (polygon.properties.is_selected === is_selected) return polygon;

      did_update = true;
      return {
        ...polygon,
        properties: {
          ...polygon.properties,
          is_selected,
        },
      };
    });

    viz_state.dendro.polygons[target_axis] = updated_polygons;

    if (layers_mat[`${target_axis}_dendro_layer`]) {
      layers_mat[`${target_axis}_dendro_layer`] = layers_mat[
        `${target_axis}_dendro_layer`
      ].clone({
        data: updated_polygons,
      });
    }
  });

  if (did_update && typeof deck_mat?.setProps === 'function') {
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }
};

/**
 * Alpha multiplier for a matrix cell / composition segment at (row, col)
 * given the current dendrogram hover/click highlight — 1 (no change) unless
 * a highlight is active and this row and/or column isn't covered by it.
 * Shared by `mat_layer.js` (heatmap/size/dotplot) and `composition_layer.js`.
 *
 * @param {object} viz_state - Visualization state.
 * @param {number} row - Raw row index.
 * @param {number} col - Raw column index.
 * @returns {number} Alpha multiplier in (0, 1].
 */
export const dendro_highlight_alpha_factor = (viz_state, row, col) => {
  const highlight = viz_state.dendro?.highlight;
  if (!highlight || (!highlight.row && !highlight.col)) return 1;

  const row_ok = !highlight.row || highlight.row.has(row);
  const col_ok = !highlight.col || highlight.col.has(col);
  return row_ok && col_ok ? 1 : DENDRO_HIGHLIGHT_DIM_ALPHA;
};

/**
 * Set (or clear) the dendrogram-driven cell/segment highlight for one axis,
 * and re-render the body layer (`mat_layer`, whichever layer class is
 * currently assigned there — heatmap/dotplot or composition) so
 * `dendro_highlight_alpha_factor` picks up the change. Uses the precomputed
 * leaf indices when available, so the per-cell render accessor is just a
 * fast `Set.has(index)` check and hover does not scan every label.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {string} axis - "row" or "col".
 * @param {string[]|object|null} highlight - Leaf names or
 *   `{indices, names}` to highlight, or null to clear.
 */
export const set_dendro_highlight = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  highlight
) => {
  viz_state.dendro.highlight = viz_state.dendro.highlight || {
    row: null,
    col: null,
  };

  let indices = null;
  const direct_indices =
    Array.isArray(highlight?.indices) && highlight.indices.length > 0
      ? highlight.indices
      : Array.isArray(highlight?.all_indices) &&
          highlight.all_indices.length > 0
        ? highlight.all_indices
        : null;

  if (direct_indices) {
    indices = new Set();
    direct_indices.forEach((value) => {
      const index = Number(value);
      if (Number.isInteger(index) && index >= 0) {
        indices.add(index);
      }
    });
  } else {
    const names = Array.isArray(highlight)
      ? highlight
      : highlight?.names || highlight?.all_names || null;

    if (Array.isArray(names) && names.length > 0) {
      const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
      const name_set = new Set(names.map((name) => String(name)));
      indices = new Set();

      nodes.forEach((node, index) => {
        if (name_set.has(String(node.name))) {
          indices.add(index);
        }
      });
    }
  }

  viz_state.dendro.highlight[axis] = indices;
  viz_state.dendro._highlight_rev = (viz_state.dendro._highlight_rev || 0) + 1;

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.mat_layer),
      getFillColor: [
        crop_filter_signature(viz_state),
        crop_fade_signature(viz_state),
        viz_state.mat?.comp_hover_row,
        viz_state.mat?.comp_hover_col,
        viz_state.dendro._highlight_rev,
      ],
    },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

const restore_axis_highlight_from_focus = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  const focus = get_axis_focus(viz_state, axis);
  const polygon = focus
    ? get_polygon_by_name(viz_state, axis, focus.name)
    : null;
  set_dendro_highlight(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    polygon?.properties || null
  );
};

// Animates a trapezoid's shape interpolating smoothly between its old and
// new leaf span, instead of snapping instantly. Deliberately used for only
// ONE thing: composition mode's PROP/COUNTS toggle (see
// `refresh_composition_dendro`'s `animate` param) — the trapezoid's
// endpoints genuinely correspond to the same leaves before and after that
// toggle, so morphing between them reads as "this shape changed," not as a
// new, unrelated shape appearing. Everywhere else a dendrogram redraws (the
// cut-level/"slice" threshold slider changing which leaves are even grouped
// together, a row/column reorder, a viz-mode switch, composition weight
// changes), the leaf groupings themselves are different, so animating
// between two different groupings just reads as trapezoids randomly
// appearing/sliding around -- those call sites all pass `animate=false`
// (the default) and get an instant snap instead. Safe to animate now that
// there's no stroke sublayer: each polygon is a fixed 3-vertex triangle, so
// the fill's per-vertex interpolation is unambiguous.
const dendro_transitions = (viz_state) => ({
  getPolygon: { duration: viz_state.animate.duration, easing: d3.easeCubic },
});

export const ini_dendro_layer = (layers_mat, viz_state, axis) => {
  const inst_layer = new PolygonLayer({
    id: `${axis}-dendro-layer`,
    data: viz_state.dendro.polygons[axis],
    getPolygon: (d) => d.coordinates,
    getFillColor: (d) => {
      if (is_dendro_crop_source(viz_state, axis, d)) {
        return CROPPED_FILL_COLOR;
      }

      if (d.properties.is_focused) {
        return FOCUSED_FILL_COLOR;
      }

      if (d.properties.is_selected) {
        return SELECTED_FILL_COLOR;
      }

      if (Array.isArray(d.properties.fill_color)) {
        return d.properties.fill_color;
      }

      return DEFAULT_FILL_COLOR;
    },
    stroked: false,
    pickable: true,
    antialiasing: false,
    transitions: dendro_transitions(viz_state),
  });

  return inst_layer;
};

/**
 * Push fresh polygon data into one axis's dendrogram layer.
 *
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {string} axis - "row" or "col".
 * @param {boolean} [animate] - Whether to morph the trapezoid shapes rather
 *   than snap instantly. Default `false` -- see `dendro_transitions` above
 *   for why only the composition PROP/COUNTS toggle passes `true`.
 */
export const update_dendro_layer_data = (
  layers_mat,
  viz_state,
  axis,
  animate = false
) => {
  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      data: viz_state.dendro.polygons[axis],
      transitions: animate ? dendro_transitions(viz_state) : false,
    }
  );
};

export const toggle_dendro_layer_visibility = (layers_mat, viz_state, axis) => {
  const layer = layers_mat[`${axis}_dendro_layer`];
  const is_visible = viz_state.order.current[axis] === 'clust';
  const was_visible = layer.props?.visible !== false;

  // Triangles/polygons are only recomputed on events that change matrix
  // geometry (crop, viz-mode switch, attribute refresh). A dendrogram hidden
  // across one of those (any custom/rank/other reorder hides it) would come
  // back with stale leaf positions, so rebuild its data as it reappears.
  if (is_visible && !was_visible) {
    calc_dendro_triangles(viz_state, axis);
    calc_dendro_polygons(viz_state, axis);
    update_dendro_layer_data(layers_mat, viz_state, axis);
  }

  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      visible: is_visible,
    }
  );
};

/**
 * Recompute BOTH axes' dendrogram triangles/polygons for the current
 * `viz_mode` and push the fresh data into both dendro layers. Call once
 * whenever `viz_mode` crosses the composition boundary — that's the only
 * time the *shape* of the leaf-position formula itself changes (composition
 * vs. uniform heatmap spacing); reorder/normalize/weight changes within
 * composition mode are handled by the narrower `refresh_composition_dendro`.
 *
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const refresh_dendro_for_viz_mode = (layers_mat, viz_state) => {
  ['row', 'col'].forEach((axis) => {
    calc_dendro_triangles(viz_state, axis);
    calc_dendro_polygons(viz_state, axis);
    update_dendro_layer_data(layers_mat, viz_state, axis);
  });
};

/**
 * Recompute just the row dendrogram's triangles/polygons in composition
 * mode — needed whenever the rightmost bar's segment positions can change:
 * column reorder (any mechanism), the PROP/COUNTS toggle, or
 * `composition_col_weights` changing. No-op outside composition mode (column
 * order there is always uniformly spaced, so its own dendrogram never needs
 * recomputing beyond the one-time `refresh_dendro_for_viz_mode` above).
 *
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {boolean} [animate] - Forwarded to `update_dendro_layer_data`.
 *   Default `false` (reorder/weight changes snap instantly); only the
 *   PROP/COUNTS toggle handler (`matrix_viz.js`'s
 *   `change:composition_normalized` listener) passes `true`, since that's
 *   the one case where the same leaves genuinely morph to a new position
 *   rather than a reorder producing an unrelated new grouping.
 */
export const refresh_composition_dendro = (
  layers_mat,
  viz_state,
  animate = false
) => {
  if (viz_state.mat.viz_mode !== 'composition') return;
  calc_dendro_triangles(viz_state, 'row');
  calc_dendro_polygons(viz_state, 'row');
  update_dendro_layer_data(layers_mat, viz_state, 'row', animate);
};

/**
 * Compute category breakdown for selected nodes.
 * Returns an object with category counts for each attribute.
 */
const compute_category_breakdown = (viz_state, axis, selected_names) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const attr_names = viz_state.attr?.names?.[axis] || [];
  const selected_set = new Set(selected_names);
  const selected_nodes = nodes.filter((node) => selected_set.has(node.name));

  const breakdown = {};

  attr_names.forEach((attr_name, attr_index) => {
    const cat_key = `cat-${attr_index}`;
    const counts = {};

    selected_nodes.forEach((node) => {
      const value = node[cat_key];
      if (value !== undefined && value !== null) {
        counts[value] = (counts[value] || 0) + 1;
      }
    });

    const breakdown_array = Object.entries(counts)
      .map(([name, count]) => ({ name, value: count }))
      .sort((a, b) => b.value - a.value);

    if (breakdown_array.length > 0) {
      breakdown[attr_name] = breakdown_array;
    }
  });

  return breakdown;
};

const build_click_value = (viz_state, axis, polygon_props, selected_names) => {
  const axis_entity =
    axis === 'row' ? viz_state.row_entity : viz_state.col_entity;

  return {
    name: polygon_props.name,
    selected_names,
    entity: axis_entity.entity,
    attr: axis_entity.attr,
    row_entity: viz_state.row_entity.entity,
    col_entity: viz_state.col_entity.entity,
    row_entity_full: viz_state.row_entity,
    col_entity_full: viz_state.col_entity,
  };
};

const maybe_open_dendro_editor = (viz_state, axis, selected_names) => {
  if (!viz_state.attr?.editor?.open) {
    return;
  }

  const editor_width = 240;
  const editor_height = 200;
  let position;

  if (axis === 'row') {
    position = {
      x:
        (viz_state.viz.row_region || 0) +
        (viz_state.viz.label_buffer || 0) +
        (viz_state.viz.mat_width || 300) -
        editor_width -
        1,
      y: (viz_state.viz.col_region || 0) + (viz_state.viz.label_buffer || 0),
    };
  } else {
    position = {
      x:
        (viz_state.viz.row_region || 0) +
        (viz_state.viz.label_buffer || 0) +
        (viz_state.viz.mat_width || 300) -
        editor_width,
      y:
        (viz_state.viz.col_region || 0) +
        (viz_state.viz.label_buffer || 0) +
        (viz_state.viz.mat_height || 300) -
        editor_height -
        1,
    };
  }

  viz_state.attr.editor.open({
    axis,
    selection: selected_names,
    position,
  });
};

const dendro_display_name = (name) => {
  const string_name = String(name);
  return string_name.includes(': ') ? string_name.split(': ')[1] : string_name;
};

const dendro_cluster_indices = (viz_state, axis, polygon_props) => {
  if (
    Array.isArray(polygon_props.all_indices) &&
    polygon_props.all_indices.length > 0
  ) {
    return polygon_props.all_indices.slice();
  }

  const selected_names = polygon_props.all_names || [];
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const name_set = new Set(
    selected_names.flatMap((name) => {
      const string_name = String(name);
      return [string_name, dendro_display_name(string_name)];
    })
  );

  const indices = [];
  nodes.forEach((node, index) => {
    const node_name = String(node.name);
    if (
      name_set.has(node_name) ||
      name_set.has(dendro_display_name(node_name))
    ) {
      indices.push(index);
    }
  });

  return indices;
};

const apply_single_click_selection = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_props
) => {
  const selected_names = polygon_props.all_names || [];
  let is_unselecting = false;
  const selected = ensure_selection_tracking(viz_state);
  const current_selection =
    viz_state.obs_store?.dendro_selection?.get?.() || selected[axis] || null;

  viz_state.click.type = `${axis}_dendro`;
  viz_state.click.value = build_click_value(
    viz_state,
    axis,
    polygon_props,
    selected_names
  );

  if (viz_state.obs_store?.dendro_selection) {
    if (
      current_selection &&
      current_selection.axis === axis &&
      current_selection.name === polygon_props.name
    ) {
      is_unselecting = true;
      viz_state.obs_store.dendro_selection.set(null);

      if (viz_state.obs_store?.category_breakdown) {
        viz_state.obs_store.category_breakdown.set({ row: {}, col: {} });
      }
    } else {
      viz_state.obs_store.dendro_selection.set({
        axis,
        name: polygon_props.name,
        selected_names,
      });

      if (viz_state.obs_store?.category_breakdown) {
        const breakdown = compute_category_breakdown(
          viz_state,
          axis,
          selected_names
        );
        viz_state.obs_store.category_breakdown.set({
          row: {},
          col: {},
          [axis]: breakdown,
        });
      }
    }
  } else if (
    current_selection &&
    current_selection.axis === axis &&
    current_selection.name === polygon_props.name
  ) {
    is_unselecting = true;
  }

  if (is_unselecting) {
    viz_state.click.value.selected_names = [];
    viz_state.click.value.is_unselecting = true;
    viz_state.attr?.editor?.close?.();
    clear_dendro_selection(deck_mat, layers_mat, viz_state);
  } else {
    apply_dendro_selection_visual(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      polygon_props.name
    );
  }

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  const names_to_sync = is_unselecting ? [] : selected_names;
  if (axis === 'row') {
    sync_selected_rows(viz_state, names_to_sync);
    sync_selected_genes(viz_state, names_to_sync);
  } else if (axis === 'col') {
    sync_selected_cols(viz_state, names_to_sync);
  }

  if (!is_unselecting) {
    maybe_open_dendro_editor(viz_state, axis, selected_names);
  }

  if (typeof viz_state.custom_callbacks[`${axis}_dendro`] === 'function') {
    viz_state.custom_callbacks[`${axis}_dendro`](names_to_sync);
  }
};

const apply_double_click_crop = (viz_state, axis, polygon_props) => {
  const indices = dendro_cluster_indices(viz_state, axis, polygon_props);

  if (!indices.length) {
    return;
  }

  viz_state.crop?.apply_axis_crop?.(axis, indices, {
    source: {
      name: polygon_props.name,
      indices,
    },
  });
};

const queue_single_click = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_props
) => {
  viz_state.dendro.pending_click[axis] = polygon_props;
  viz_state.dendro.click_timeouts[axis] = setTimeout(() => {
    const pending = viz_state.dendro.pending_click[axis];
    viz_state.dendro.pending_click[axis] = null;
    viz_state.dendro.click_timeouts[axis] = null;

    if (pending) {
      apply_single_click_selection(
        deck_mat,
        layers_mat,
        viz_state,
        axis,
        pending
      );
    }
  }, DOUBLE_CLICK_DELAY);
};

// Double-click detection rests entirely on the pending-click timer: a second
// click on the same trapezoid within DOUBLE_CLICK_DELAY crops. The browser's
// native `detail` counter is deliberately not used — its ~500ms window
// outlives the 350ms timer, so a slower second click (which the user means as
// a toggle-off of the applied selection) would crop instead.
const handle_dendro_polygon_click = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_props
) => {
  if (!axis || !polygon_props) {
    return;
  }

  ensure_click_tracking(viz_state);
  const pending = viz_state.dendro.pending_click[axis];

  if (!viz_state.dendro.click_timeouts[axis]) {
    queue_single_click(deck_mat, layers_mat, viz_state, axis, polygon_props);
    return;
  }

  clear_pending_axis_click(viz_state, axis);

  if (pending?.name === polygon_props.name) {
    apply_double_click_crop(viz_state, axis, polygon_props);
    return;
  }

  apply_single_click_selection(deck_mat, layers_mat, viz_state, axis, pending);
  queue_single_click(deck_mat, layers_mat, viz_state, axis, polygon_props);
};

// Strict (no-tolerance) containment: only clicks that land inside a
// dendrogram viewport are treated as dendrogram clicks. Without this gate,
// pickObject's pick radius would also claim clicks in the adjacent band of
// matrix cells, which deck.gl has already delivered to the cell onClick —
// double-handling one physical click.
const point_in_dendro_viewport_bounds = (deck_mat, x, y) => {
  const viewports = deck_mat.viewManager?.getViewports?.() || [];
  return viewports.some(
    (viewport) =>
      (viewport.id === 'dendro_rows' || viewport.id === 'dendro_cols') &&
      x >= viewport.x &&
      x <= viewport.x + viewport.width &&
      y >= viewport.y &&
      y <= viewport.y + viewport.height
  );
};

const pick_dendro_polygon_at = (deck_mat, layers_mat, viz_state, x, y) => {
  if (!point_in_dendro_viewport_bounds(deck_mat, x, y)) {
    return { axis: null, polygon_props: null };
  }

  if (typeof deck_mat.pickObject === 'function') {
    const info = deck_mat.pickObject({
      x,
      y,
      radius: 8,
      layerIds: ['row-dendro-layer', 'col-dendro-layer'],
    });
    const axis =
      info?.layer?.id === 'row-dendro-layer'
        ? 'row'
        : info?.layer?.id === 'col-dendro-layer'
          ? 'col'
          : null;
    const polygon_props = polygon_props_from_pick_info(info);

    if (
      axis &&
      polygon_props &&
      dendro_axis_is_interactive(layers_mat, viz_state, axis)
    ) {
      return { axis, polygon_props };
    }
  }

  return manual_pick_dendro_polygon(deck_mat, layers_mat, viz_state, x, y);
};

// A DOM 'click' fires on mouseup even after a drag (there is no movement
// threshold in the click event, unlike deck.gl's tap recognizer), so a pan
// that ends over a trapezoid would register as a selection. Track the
// pointer-down position and ignore clicks that moved more than a few pixels.
const DENDRO_CLICK_MAX_DRAG_PX = 5;

const ensure_native_dendro_click = (deck_mat, layers_mat, viz_state) => {
  if (viz_state.dendro._native_click_handler) {
    return;
  }

  viz_state.dendro._native_pointerdown_handler = (native_event) => {
    viz_state.dendro._native_click_start = {
      x: native_event.clientX,
      y: native_event.clientY,
    };
  };

  viz_state.dendro._native_click_handler = (native_event) => {
    if (native_event.button > 0) return;

    const start = viz_state.dendro._native_click_start;
    if (
      start &&
      (Math.abs(native_event.clientX - start.x) > DENDRO_CLICK_MAX_DRAG_PX ||
        Math.abs(native_event.clientY - start.y) > DENDRO_CLICK_MAX_DRAG_PX)
    ) {
      return;
    }

    const rect =
      deck_mat.canvas?.getBoundingClientRect?.() ||
      viz_state.root?.getBoundingClientRect?.();
    if (!rect) return;

    const x = native_event.clientX - rect.left;
    const y = native_event.clientY - rect.top;
    const { axis, polygon_props } = pick_dendro_polygon_at(
      deck_mat,
      layers_mat,
      viz_state,
      x,
      y
    );
    if (!axis || !polygon_props) return;

    native_event.preventDefault();
    native_event.stopPropagation();
    native_event.stopImmediatePropagation?.();

    handle_dendro_polygon_click(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      polygon_props
    );
  };

  viz_state.root?.addEventListener?.(
    'pointerdown',
    viz_state.dendro._native_pointerdown_handler,
    true
  );
  viz_state.root?.addEventListener?.(
    'click',
    viz_state.dendro._native_click_handler,
    true
  );
};

export const set_dendro_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  ensure_native_dendro_click(deck_mat, layers_mat, viz_state);

  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      onClick: () => true,
    }
  );
};

/**
 * Wire up hover-to-highlight for a dendrogram trapezoid: hovering a leaf
 * group highlights every row/column it covers (dimming everything else)
 * after a short dwell delay, so a quick pass-over doesn't flash; moving off
 * restores any persistent crop/focus highlight for that axis.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {string} axis - "row" or "col".
 */
export const set_dendro_layer_onhover = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  const on_hover = (info) => {
    clearTimeout(viz_state.dendro._hover_timer);

    const properties = info?.object?.properties || null;
    const hover_payload =
      properties &&
      ((Array.isArray(properties.all_indices) &&
        properties.all_indices.length > 0) ||
        (Array.isArray(properties.all_names) &&
          properties.all_names.length > 0))
        ? properties
        : null;
    const hover_name = properties?.name || null;

    if (!hover_payload) {
      if (viz_state.dendro._hover_target?.axis === axis) {
        viz_state.dendro._hover_target = null;
      }
      restore_axis_highlight_from_focus(deck_mat, layers_mat, viz_state, axis);
      return;
    }

    const hover_target = { axis, name: hover_name };
    viz_state.dendro._hover_target = hover_target;

    viz_state.dendro._hover_timer = setTimeout(() => {
      const current_target = viz_state.dendro._hover_target;
      if (
        current_target?.axis !== hover_target.axis ||
        current_target?.name !== hover_target.name
      ) {
        return;
      }
      set_dendro_highlight(
        deck_mat,
        layers_mat,
        viz_state,
        axis,
        hover_payload
      );
    }, DENDRO_HOVER_DELAY_MS);
  };

  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      onHover: on_hover,
    }
  );
};

/**
 * Force-clear the dendrogram hover highlight (both axes), cancelling any
 * pending delayed-highlight timer first. Without cancelling the timer, a
 * highlight already armed (but not yet applied) when the pointer leaves
 * would otherwise still fire a few hundred ms later, highlighting leaves the
 * pointer isn't over anymore. Safe to call unconditionally (e.g. from a
 * whole-widget pointer-leave failsafe) even when nothing is hovered.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const clear_dendro_hover = (deck_mat, layers_mat, viz_state) => {
  clearTimeout(viz_state.dendro._hover_timer);
  viz_state.dendro._hover_target = null;
  DENDRO_AXES.forEach((axis) => {
    if (layers_mat[`${axis}_dendro_layer`]) {
      restore_axis_highlight_from_focus(deck_mat, layers_mat, viz_state, axis);
    }
  });
};
