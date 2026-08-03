import * as d3 from 'd3';
import { PolygonLayer } from 'deck.gl';

import {
  sync_selected_genes,
  sync_selected_rows,
  sync_selected_cols,
} from '../../global_variables/selected_genes';
import {
  calc_dendro_triangles,
  calc_dendro_polygons,
} from '../../matrix/dendro';

import { get_mat_layers_list } from './matrix_layers';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const FOCUSED_FILL_COLOR = [0, 0, 0, 180];

// Non-covered cells/segments are dimmed to this fraction of their normal
// alpha while a dendrogram trapezoid is hovered or clicked.
const DENDRO_HIGHLIGHT_DIM_ALPHA = 0.2;

// Hover must dwell this long before the highlight kicks in (matches
// composition's cross-bar hover-highlight delay); leaving clears instantly.
const DENDRO_HOVER_DELAY_MS = 250;

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

const get_current_focus = (viz_state) => {
  const store_focus =
    viz_state?.obs_store?.focused_dendro &&
    typeof viz_state.obs_store.focused_dendro.get === 'function'
      ? viz_state.obs_store.focused_dendro.get()
      : null;

  return store_focus ?? viz_state.dendro?.active_polygon ?? null;
};

const apply_dendro_focus = (deck_mat, layers_mat, viz_state, focus) => {
  const normalized_focus = focus
    ? { axis: focus.axis, name: focus.name }
    : null;

  let did_update = false;

  DENDRO_AXES.forEach((targetAxis) => {
    if (!viz_state.dendro.polygons[targetAxis]) {
      return;
    }

    const updated_polygons = viz_state.dendro.polygons[targetAxis].map(
      (polygon) => {
        const is_focused =
          !!normalized_focus &&
          polygon.properties.axis === normalized_focus.axis &&
          polygon.properties.name === normalized_focus.name;

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

    viz_state.dendro.polygons[targetAxis] = updated_polygons;

    if (layers_mat[`${targetAxis}_dendro_layer`]) {
      layers_mat[`${targetAxis}_dendro_layer`] = layers_mat[
        `${targetAxis}_dendro_layer`
      ].clone({
        data: updated_polygons,
      });
    }
  });

  viz_state.dendro.active_polygon = normalized_focus;

  if (viz_state.obs_store?.focused_dendro) {
    const focus_value = normalized_focus ? { ...normalized_focus } : null;
    viz_state.obs_store.focused_dendro.set(focus_value);
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
    const name_set = new Set(names);
    indices = new Set();
    nodes.forEach((node, i) => {
      if (name_set.has(String(node.name))) indices.add(i);
    });
  }

  viz_state.dendro.highlight[axis] = indices;
  viz_state.dendro._highlight_rev = (viz_state.dendro._highlight_rev || 0) + 1;

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: { getFillColor: viz_state.dendro._highlight_rev },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
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
    // No outline: it was purely decorative, and having it as a second,
    // separately-pickable sublayer (fill + stroke) was a source of picking
    // instability — hovering across the fill/stroke boundary counted as
    // leaving one sublayer and entering another, firing a spurious
    // out-then-in onHover pair. A single fill-only shape is simpler to pick
    // correctly.
    stroked: false,
    pickable: true,
    antialiasing: false,
    // Inert at construction time (nothing to transition from yet) -- the
    // transitions that matter are the ones passed per-update below.
    transitions: dendro_transitions(viz_state),
    // autoHighlight: true, // Highlight on hover
    // onHover: ({ object }) => console.log(object?.properties.name), // Hover info
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
  // if viz_state.order.curent[axis] is 'clust' then the dendrogram is visible.
  // In composition mode the row dendrogram's leaves are positioned from the
  // rightmost bar's actual segments (see refresh_composition_dendro below),
  // so it's just as meaningful as in heatmap mode — no special-case needed.
  const is_visible = viz_state.order.current[axis] === 'clust';

  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      // visible: !layers_mat[axis + '_dendro_layer'].visible,
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

const focus_dendro_polygon = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygonName
) => {
  const previous_focus = get_current_focus(viz_state);

  if (
    previous_focus &&
    previous_focus.axis === axis &&
    previous_focus.name === polygonName
  ) {
    apply_dendro_focus(deck_mat, layers_mat, viz_state, null);
    return;
  }

  apply_dendro_focus(deck_mat, layers_mat, viz_state, {
    axis,
    name: polygonName,
  });
};

/**
 * Compute category breakdown for selected nodes.
 * Returns an object with category counts for each attribute.
 */
const compute_category_breakdown = (viz_state, axis, selected_names) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const attr_names = viz_state.attr?.names?.[axis] || [];

  // Find the selected node indices
  const selected_set = new Set(selected_names);
  const selected_nodes = nodes.filter((node) => selected_set.has(node.name));

  const breakdown = {};

  // For each attribute, count the category values
  attr_names.forEach((attr_name, attr_index) => {
    const cat_key = `cat-${attr_index}`;
    const counts = {};

    selected_nodes.forEach((node) => {
      const value = node[cat_key];
      if (value !== undefined && value !== null) {
        counts[value] = (counts[value] || 0) + 1;
      }
    });

    // Convert to array sorted by count
    const breakdown_array = Object.entries(counts)
      .map(([name, count]) => ({ name, value: count }))
      .sort((a, b) => b.value - a.value);

    if (breakdown_array.length > 0) {
      breakdown[attr_name] = breakdown_array;
    }
  });

  return breakdown;
};

const dendro_layer_onclick = (event, deck_mat, layers_mat, viz_state, axis) => {
  viz_state.click.type = `${axis}_dendro`;

  // Get the entity info for the clicked axis
  const axis_entity =
    axis === 'row' ? viz_state.row_entity : viz_state.col_entity;
  const selected_names = event.object.properties.all_names || [];

  viz_state.click.value = {
    name: event.object.properties.name,
    selected_names,
    // New structured entity info for the clicked axis
    entity: axis_entity.entity,
    attr: axis_entity.attr,
    // Legacy fields for backwards compatibility
    row_entity: viz_state.row_entity.entity,
    col_entity: viz_state.col_entity.entity,
    // Full entity info for both axes (for advanced use cases)
    row_entity_full: viz_state.row_entity,
    col_entity_full: viz_state.col_entity,
  };

  focus_dendro_polygon(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    event.object.properties.name
  );

  // focus_dendro_polygon just toggled active_polygon; mirror that into the
  // cell/segment highlight (clicking the already-focused polygon clears it).
  const is_now_focused =
    viz_state.dendro.active_polygon?.axis === axis &&
    viz_state.dendro.active_polygon?.name === event.object.properties.name;
  set_dendro_highlight(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    is_now_focused ? selected_names : null
  );

  // Update dendro_selection in the store
  let is_unselecting = false;
  if (viz_state.obs_store?.dendro_selection) {
    const current = viz_state.obs_store.dendro_selection.get();
    // Toggle off if clicking the same dendro
    if (
      current &&
      current.axis === axis &&
      current.name === event.object.properties.name
    ) {
      is_unselecting = true;
      viz_state.obs_store.dendro_selection.set(null);
      // Reset category breakdown
      if (viz_state.obs_store?.category_breakdown) {
        viz_state.obs_store.category_breakdown.set({ row: {}, col: {} });
      }
    } else {
      viz_state.obs_store.dendro_selection.set({
        axis,
        name: event.object.properties.name,
        selected_names,
      });

      // Compute and update category breakdown
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

  // If unselecting, update click_info with empty selected_names
  // so the Landscape handler knows to clear the cells
  if (is_unselecting) {
    viz_state.click.value.selected_names = [];
    viz_state.click.value.is_unselecting = true;

    // Close the editor when unselecting
    if (viz_state.attr?.editor?.close) {
      viz_state.attr.editor.close();
    }
  }

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  // Sync selected rows/cols to Python model
  // If unselecting, clear the selections
  const names_to_sync = is_unselecting ? [] : selected_names;
  if (axis === 'row') {
    sync_selected_rows(viz_state, names_to_sync);
    // Also sync to selected_genes for backwards compatibility
    sync_selected_genes(viz_state, names_to_sync);
  } else if (axis === 'col') {
    sync_selected_cols(viz_state, names_to_sync);
  }

  // Open editor positioned 1px left of row dendro or 1px above col dendro
  if (viz_state.attr?.editor?.open && !is_unselecting) {
    const editor_width = 240;
    const editor_height = 200;
    let position;
    if (axis === 'row') {
      // Row dendro is on the right - position editor 1px to the left of it
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
      // Col dendro is at the bottom - position editor 1px above it
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
  }

  if (typeof viz_state.custom_callbacks[`${axis}_dendro`] === 'function') {
    viz_state.custom_callbacks[`${axis}_dendro`](selected_names);
  }
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
 * clears the highlight immediately. Independent of click-focus — hovering a
 * different trapezoid while one is click-focused just temporarily shows the
 * hovered group's coverage instead.
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
      set_dendro_highlight(deck_mat, layers_mat, viz_state, axis, null);
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
      set_dendro_highlight(deck_mat, layers_mat, viz_state, axis, null);
    }
  });
};
