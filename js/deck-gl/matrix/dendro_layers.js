import * as d3 from 'd3';
import { LinearInterpolator, PolygonLayer } from 'deck.gl';

import {
  sync_selected_genes,
  sync_selected_rows,
  sync_selected_cols,
} from '../../global_variables/selected_genes';
import {
  calc_dendro_triangles,
  calc_dendro_polygons,
} from '../../matrix/dendro';

import { curate_pan_x, curate_pan_y } from './curate_pan';
import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { update_zoom_data } from './zoom';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const FOCUSED_FILL_COLOR = [0, 0, 0, 180];
const DOUBLE_CLICK_DELAY = 250;
const DENDRO_FOCUS_TRANSITION = 650;
const DENDRO_HIGHLIGHT_DIM_ALPHA = 0.2;
const DENDRO_HOVER_DELAY_MS = 250;

const ease_out_cubic = (t) => 1 - Math.pow(1 - t, 3);

const get_layer_update_triggers = (layer) => layer?.props?.updateTriggers || {};

const ensure_click_tracking = (viz_state) => {
  if (!viz_state.dendro.click_timeouts) {
    viz_state.dendro.click_timeouts = { row: null, col: null };
  }

  if (!viz_state.dendro.pending_click) {
    viz_state.dendro.pending_click = { row: null, col: null };
  }
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

const is_axis_focused = (viz_state, axis, polygon_name) =>
  get_axis_focus(viz_state, axis)?.name === polygon_name;

const get_polygon_by_name = (viz_state, axis, polygon_name) =>
  viz_state.dendro.polygons?.[axis]?.find(
    (polygon) => polygon.properties.name === polygon_name
  );

const transition_view_state = (view_state) =>
  Object.fromEntries(
    Object.entries(view_state).map(([key, value]) => [
      key,
      {
        ...value,
        transitionDuration: DENDRO_FOCUS_TRANSITION,
        transitionEasing: ease_out_cubic,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
      },
    ])
  );

const apply_zoom_state = (
  deck_mat,
  layers_mat,
  viz_state,
  view_id,
  zoom_curated,
  pan_curated
) => {
  const global_view_state = redefine_global_view_state(
    viz_state,
    view_id,
    zoom_curated,
    pan_curated
  );

  update_zoom_data(viz_state, view_id, zoom_curated, pan_curated);
  viz_state.zoom.zoom_data.total_zoom.x = zoom_curated[0];
  viz_state.zoom.zoom_data.total_zoom.y = zoom_curated[1];

  deck_mat.setProps({
    viewState: transition_view_state(global_view_state),
    layers: get_mat_layers_list(layers_mat),
  });
};

const animate_focus_to_cluster = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_props
) => {
  if (!polygon_props) {
    return;
  }

  const current = viz_state.zoom.zoom_data.matrix;
  const is_row_axis = axis === 'row';
  const matrix_span = is_row_axis
    ? viz_state.viz.mat_height
    : viz_state.viz.mat_width;
  const min_unit = is_row_axis
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;
  const cluster_span = Math.max(
    Math.abs((polygon_props.pos_bot ?? 0) - (polygon_props.pos_top ?? 0)),
    min_unit
  );
  const target_zoom = Math.max(0, Math.log2(matrix_span / cluster_span));
  const cluster_center =
    ((polygon_props.pos_top ?? 0) + (polygon_props.pos_bot ?? 0)) / 2;

  const zoom_curated = [
    is_row_axis ? current.zoom_x : target_zoom,
    is_row_axis ? target_zoom : current.zoom_y,
  ];
  const pan_curated = [
    curate_pan_x(
      is_row_axis ? current.pan_x : cluster_center,
      zoom_curated[0],
      viz_state
    ),
    curate_pan_y(
      is_row_axis ? cluster_center : current.pan_y,
      zoom_curated[1],
      viz_state
    ),
  ];

  apply_zoom_state(
    deck_mat,
    layers_mat,
    viz_state,
    is_row_axis ? 'dendro_rows' : 'dendro_cols',
    zoom_curated,
    pan_curated
  );
};

const animate_focus_reset_axis = (deck_mat, layers_mat, viz_state, axis) => {
  const current = viz_state.zoom.zoom_data.matrix;
  const is_row_axis = axis === 'row';

  const zoom_curated = [
    is_row_axis ? current.zoom_x : viz_state.zoom.ini_zoom_x,
    is_row_axis ? viz_state.zoom.ini_zoom_y : current.zoom_y,
  ];
  const pan_curated = [
    curate_pan_x(
      is_row_axis ? current.pan_x : viz_state.zoom.ini_pan_x,
      zoom_curated[0],
      viz_state
    ),
    curate_pan_y(
      is_row_axis ? viz_state.zoom.ini_pan_y : current.pan_y,
      zoom_curated[1],
      viz_state
    ),
  ];

  apply_zoom_state(
    deck_mat,
    layers_mat,
    viz_state,
    is_row_axis ? 'dendro_rows' : 'dendro_cols',
    zoom_curated,
    pan_curated
  );
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

const apply_dendro_focus = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_name
) => {
  const next_focus = get_current_focus_map(viz_state);
  next_focus[axis] = polygon_name ? { axis, name: polygon_name } : null;

  let did_update = false;

  DENDRO_AXES.forEach((target_axis) => {
    if (!viz_state.dendro.polygons[target_axis]) {
      return;
    }

    const focused_name = next_focus[target_axis]?.name || null;
    const updated_polygons = viz_state.dendro.polygons[target_axis].map(
      (polygon) => {
        const is_focused = polygon.properties.name === focused_name;

        if (polygon.properties.is_focused === is_focused) {
          return polygon;
        }

        did_update = true;

        return {
          ...polygon,
          properties: {
            ...polygon.properties,
            is_focused,
          },
        };
      }
    );

    viz_state.dendro.polygons[target_axis] = updated_polygons;

    if (layers_mat[`${target_axis}_dendro_layer`]) {
      layers_mat[`${target_axis}_dendro_layer`] = layers_mat[
        `${target_axis}_dendro_layer`
      ].clone({
        data: updated_polygons,
      });
    }
  });

  viz_state.dendro.active_polygon = next_focus;

  if (viz_state.obs_store?.focused_dendro) {
    viz_state.obs_store.focused_dendro.set(next_focus);
  }

  if (did_update && typeof deck_mat?.setProps === 'function') {
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }
};

/**
 * Set (or clear) the dendrogram-driven cell/segment highlight for one axis,
 * and re-render the body layer (`mat_layer`, whichever layer class is
 * currently assigned there — heatmap/dotplot or composition) so
 * `dendro_highlight_alpha_factor` picks up the change. Converts the leaf
 * name list into an index set once here, so the per-cell render accessor is
 * just a fast `Set.has(index)` check.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {string} axis - "row" or "col".
 * @param {string[]|null} names - Leaf names to highlight, or null to clear.
 */
export const set_dendro_highlight = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  names
) => {
  viz_state.dendro.highlight = viz_state.dendro.highlight || {
    row: null,
    col: null,
  };

  let indices = null;
  if (names) {
    const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
    const name_set = new Set(names.map((name) => String(name)));
    indices = new Set();
    nodes.forEach((node, index) => {
      if (name_set.has(String(node.name))) {
        indices.add(index);
      }
    });
  }

  viz_state.dendro.highlight[axis] = indices;
  viz_state.dendro._highlight_rev = (viz_state.dendro._highlight_rev || 0) + 1;

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.mat_layer),
      getFillColor: viz_state.dendro._highlight_rev,
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
    polygon?.properties?.all_names || null
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
      if (d.properties.is_focused) {
        return FOCUSED_FILL_COLOR;
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
  const is_visible = viz_state.order.current[axis] === 'clust';

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

const apply_single_click_selection = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_props
) => {
  const selected_names = polygon_props.all_names || [];
  let is_unselecting = false;

  viz_state.click.type = `${axis}_dendro`;
  viz_state.click.value = build_click_value(
    viz_state,
    axis,
    polygon_props,
    selected_names
  );

  if (viz_state.obs_store?.dendro_selection) {
    const current = viz_state.obs_store.dendro_selection.get();

    if (
      current &&
      current.axis === axis &&
      current.name === polygon_props.name
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
        const current_breakdown =
          viz_state.obs_store.category_breakdown.get() || { row: {}, col: {} };
        viz_state.obs_store.category_breakdown.set({
          ...current_breakdown,
          [axis]: breakdown,
        });
      }
    }
  }

  if (is_unselecting) {
    viz_state.click.value.selected_names = [];
    viz_state.click.value.is_unselecting = true;
    viz_state.attr?.editor?.close?.();
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

const apply_double_click_focus = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_props
) => {
  if (is_axis_focused(viz_state, axis, polygon_props.name)) {
    apply_dendro_focus(deck_mat, layers_mat, viz_state, axis, null);
    set_dendro_highlight(deck_mat, layers_mat, viz_state, axis, null);
    animate_focus_reset_axis(deck_mat, layers_mat, viz_state, axis);
    return;
  }

  apply_dendro_focus(deck_mat, layers_mat, viz_state, axis, polygon_props.name);
  set_dendro_highlight(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    polygon_props.all_names || null
  );
  animate_focus_to_cluster(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    polygon_props
  );
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

const dendro_layer_onclick = (event, deck_mat, layers_mat, viz_state, axis) => {
  ensure_click_tracking(viz_state);

  const polygon_props = {
    ...event.object.properties,
    all_names: [...(event.object.properties.all_names || [])],
  };
  const pending = viz_state.dendro.pending_click[axis];

  if (!viz_state.dendro.click_timeouts[axis]) {
    queue_single_click(deck_mat, layers_mat, viz_state, axis, polygon_props);
    return;
  }

  clearTimeout(viz_state.dendro.click_timeouts[axis]);
  viz_state.dendro.click_timeouts[axis] = null;
  viz_state.dendro.pending_click[axis] = null;

  if (pending?.name === polygon_props.name) {
    apply_double_click_focus(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      polygon_props
    );
    return;
  }

  apply_single_click_selection(deck_mat, layers_mat, viz_state, axis, pending);
  queue_single_click(deck_mat, layers_mat, viz_state, axis, polygon_props);
};

export const set_dendro_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      onClick: (event) =>
        dendro_layer_onclick(event, deck_mat, layers_mat, viz_state, axis),
    }
  );
};

/**
 * Wire up hover-to-highlight for a dendrogram trapezoid: hovering a leaf
 * group highlights every row/column it covers (dimming everything else)
 * after a short dwell delay, so a quick pass-over doesn't flash; moving off
 * restores any persistent double-click zoom highlight for that axis.
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

    const names = info?.object ? info.object.properties.all_names : null;

    if (!names) {
      restore_axis_highlight_from_focus(deck_mat, layers_mat, viz_state, axis);
      return;
    }

    viz_state.dendro._hover_timer = setTimeout(() => {
      set_dendro_highlight(deck_mat, layers_mat, viz_state, axis, names);
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
  DENDRO_AXES.forEach((axis) => {
    if (layers_mat[`${axis}_dendro_layer`]) {
      restore_axis_highlight_from_focus(deck_mat, layers_mat, viz_state, axis);
    }
  });
};
