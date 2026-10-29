import * as d3 from 'd3';

import { colorToRgba } from './cat_data';
import {
  crop_filter_signature,
  get_axis_center_position,
  get_axis_display_index,
  get_axis_display_state,
  get_axis_label_font_size,
  get_axis_slot_size,
} from './crop_filter';

// Composition (stacked-bar) layout for the Clustergram body.
//
// A "composition" Clustergram reuses the same matrix (rows = populations,
// columns = groups/datasets) but renders each COLUMN as a vertical stacked bar:
// every row (population) becomes a segment whose height is its share of that
// column, colored by the population. The heatmap-body machinery (order model,
// column attribute bars, labels, reorder) is reused unchanged; only the body
// geometry differs, so this module just computes per-cell rectangles that honor
// the current row/col order.

const FALLBACK_PALETTE = (n) =>
  n <= 10
    ? d3.schemeTableau10.slice(0, Math.max(n, 1))
    : d3.quantize((t) => d3.interpolateSinebow(t * 0.85), Math.max(n, 1));

/**
 * Precompute one RGB color per row (population), stored on
 * `viz_state.mat.comp_colors`. Resolution order: an explicit
 * `composition_colors` map from Python, then the shared `global_cat_colors`
 * registry, then an auto palette.
 *
 * @param {object} viz_state - Visualization state.
 */
export const set_composition_colors = (viz_state) => {
  const nodes = viz_state.row_nodes || [];
  const explicit =
    (viz_state.model &&
      typeof viz_state.model.get === 'function' &&
      viz_state.model.get('composition_colors')) ||
    {};
  const global_cat = viz_state.global_cat_colors || {};
  const fallback = FALLBACK_PALETTE(nodes.length);

  viz_state.mat.comp_colors = nodes.map((node, i) => {
    const name = String(node.name);
    const hex =
      explicit[name] || global_cat[name] || fallback[i % fallback.length];
    return colorToRgba(hex, 255);
  });
};

const order_signature = (viz_state) => {
  const row_key = viz_state.order.current.row;
  const col_key = viz_state.order.current.col;
  const row_arr = viz_state.mat.orders.row[row_key] || [];
  const col_arr = viz_state.mat.orders.col[col_key] || [];
  const normalized = viz_state.mat.composition_normalized ? 1 : 0;
  const weights = viz_state.mat.composition_col_weights || {};
  const weights_sig = Object.keys(weights)
    .sort()
    .map((k) => `${k}:${weights[k]}`)
    .join(',');
  return `${row_key}|${col_key}|${normalized}|${weights_sig}|${crop_filter_signature(
    viz_state
  )}|${row_arr.join(',')}|${col_arr.join(',')}`;
};

/**
 * Build the stacked-bar geometry for every (row, col) cell under the current
 * order and normalization. Returns a map keyed `"row_col"` -> {position, half},
 * where `position` is the segment center and `half` is [halfWidth, halfHeight]
 * in world units (matching the ScatterplotLayer unit-quad convention).
 *
 * @param {object} viz_state - Visualization state.
 * @returns {Record<string, {position: number[], half: number[]}>}
 */
export const build_composition_layout = (viz_state) => {
  const { num_cols, net_mat, orders, composition_normalized } = viz_state.mat;
  const { mat_height } = viz_state.viz;
  const row_order = orders.row[viz_state.order.current.row];
  const normalized = composition_normalized;
  const row_state = get_axis_display_state(viz_state, 'row');
  const col_state = get_axis_display_state(viz_state, 'col');
  const visible_rows = row_state.visible_indices;
  const visible_cols = col_state.visible_indices;
  const row_slot = get_axis_slot_size(viz_state, 'row');
  const col_slot = get_axis_slot_size(viz_state, 'col');

  // Column sums (only non-negative contributions stack).
  const col_sums = new Array(num_cols).fill(0);
  for (const r of visible_rows) {
    const row = net_mat[r];
    for (const c of visible_cols) {
      const v = row[c];
      if (v > 0) col_sums[c] += v;
    }
  }

  // Per-column magnitude for non-normalized ("counts") mode: an explicit
  // weight (e.g. a dataset's true cell count from `composition_col_weights`)
  // when available, else the column's own sum. When no explicit weights are
  // provided this reduces to exactly the previous (weights-less) formula, so
  // a matrix that already holds raw counts behaves identically either way —
  // explicit weights only matter when the matrix holds proportions (every
  // column summing to ~1) and true magnitude would otherwise be lost.
  const col_weights_by_name = viz_state.mat.composition_col_weights || {};
  const col_weights = new Array(num_cols).fill(0);
  visible_cols.forEach((c) => {
    const name = viz_state.col_nodes[c]?.name;
    const explicit = name != null ? col_weights_by_name[name] : undefined;
    col_weights[c] = explicit != null ? explicit : col_sums[c];
  });
  const max_weight = Math.max(...visible_cols.map((c) => col_weights[c]), 1e-9);

  const y_top = row_slot * 1.0; // top edge of the body region
  const half_width = col_slot * 0.5 * 0.95; // small (5%) gap between bars

  // Stack rows in the SAME order across every bar (row identity always maps
  // to the same relative vertical band everywhere), driven by the shared
  // "POP:" row order. Ascending by row_order — so double-clicking a column
  // (which ranks the highest value as the largest row_order via the generic
  // custom_label_reorder) puts that column's largest population at the
  // bottom, matching the standard bar-chart "biggest at the base" look —
  // without making each bar sort independently by its own local values.
  const rows_sorted = visible_rows
    .slice()
    .sort((a, b) => row_order[a] - row_order[b]);

  const layout = {};
  for (const c of visible_cols) {
    const x_center = get_axis_center_position(viz_state, 'col', c);
    if (x_center === null) continue;
    const col_sum = col_sums[c] || 1;
    // Bar's own height: full mat_height when normalized, else scaled by its
    // share of the largest column weight (so datasets with more cells get
    // taller bars, even when `net_mat` itself holds proportions).
    const bar_height = normalized
      ? mat_height
      : (col_weights[c] / max_weight) * mat_height;

    // Anchor at a shared bottom edge (y_top + mat_height), stacking upward —
    // the standard bar-chart convention — rather than a shared top edge, so
    // a shorter (non-normalized) bar leaves empty space above it, not below.
    let cursor = y_top + (mat_height - bar_height);
    for (const r of rows_sorted) {
      const v = Math.max(0, net_mat[r][c] || 0);
      const share = v / col_sum;
      const seg_h = share * bar_height;
      layout[`${r}_${c}`] = {
        position: [x_center, cursor + seg_h / 2],
        half: [half_width, seg_h / 2],
      };
      cursor += seg_h;
    }
  }
  return layout;
};

/**
 * Memoized accessor for the composition layout, rebuilt only when the order or
 * normalization changes.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {Record<string, {position: number[], half: number[]}>}
 */
export const get_composition_layout = (viz_state) => {
  const sig = order_signature(viz_state);
  const cache = viz_state.mat._comp_cache;
  if (cache && cache.sig === sig) return cache.layout;
  const layout = build_composition_layout(viz_state);
  viz_state.mat._comp_cache = { sig, layout };
  return layout;
};

/** Geometry for a single matrix point in composition mode. */
export const comp_geom_for = (viz_state, d) => {
  const layout = get_composition_layout(viz_state);
  return layout[`${d.row}_${d.col}`] || { position: [0, 0], half: [0, 0] };
};

const edge_composition_col = (viz_state, is_better) => {
  const visible_cols = get_axis_display_state(viz_state, 'col').visible_indices;

  let best_col = visible_cols[0] ?? 0;
  let best_x_index = null;
  for (const c of visible_cols) {
    const x_index = get_axis_display_index(viz_state, 'col', c);
    if (x_index === null) continue;
    if (best_x_index === null || is_better(x_index, best_x_index)) {
      best_x_index = x_index;
      best_col = c;
    }
  }
  return best_col;
};

/**
 * The currently-leftmost displayed column (smallest displayed x_index under
 * the current col order). Used both to decide which row labels fit and to
 * position them next to that bar.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {number} Raw column index.
 */
export const leftmost_composition_col = (viz_state) =>
  edge_composition_col(viz_state, (x_index, best) => x_index < best);

/**
 * The currently-rightmost displayed column (largest displayed x_index under
 * the current col order). Used to dynamically position the row dendrogram in
 * composition mode, which sits to the right of the matrix body.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {number} Raw column index.
 */
export const rightmost_composition_col = (viz_state) =>
  edge_composition_col(viz_state, (x_index, best) => x_index > best);

// A row label is hidden unless its segment is at least one line of text
// tall. In composition mode the row label's `getSize` is a fixed screen-pixel
// value — unlike heatmap mode, it is deliberately NOT rescaled by the `rows`
// viewport's 2^zoom_y factor (see `on_view_state_change.js`) — so zooming in
// grows a segment's on-screen height without growing the label past it,
// letting small populations' labels reveal themselves as the user zooms in.
// That means, unlike the heatmap case, this fit ratio is zoom-DEPENDENT and
// must be recomputed on every zoom tick, not just on layout changes.
const MIN_FIT_RATIO = 1.0;

const composition_row_zoom_factor = (viz_state) =>
  2 ** (viz_state.zoom?.zoom_data?.matrix?.zoom_y || 0);

/**
 * Per-row visibility for population (row) labels in composition mode: hidden
 * whenever the leftmost displayed bar's segment for that row is too short to
 * fit one line of label text at the current zoom (or absent entirely), so
 * small populations' labels don't overlap/overflow their segment — but do
 * reappear once zooming in on rows gives them enough room.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {boolean[]} Indexed by raw row index (matches `row_label_data[i].index`).
 */
export const compute_row_label_visibility = (viz_state) => {
  const { num_rows } = viz_state.mat;
  const layout = get_composition_layout(viz_state);
  const leftmost_col = leftmost_composition_col(viz_state);
  const zoom_factor = composition_row_zoom_factor(viz_state);
  const min_height =
    (get_axis_label_font_size(viz_state, 'row') * MIN_FIT_RATIO) / zoom_factor;

  const visible = new Array(num_rows).fill(false);
  get_axis_display_state(viz_state, 'row').visible_indices.forEach((r) => {
    const seg = layout[`${r}_${leftmost_col}`];
    visible[r] = !!seg && seg.half[1] * 2 >= min_height;
  });
  return visible;
};

/**
 * Row label position in composition mode: next to the leftmost bar, at that
 * row's actual segment center (rather than a uniform heatmap-style slot), so
 * labels track both reordering and normalization exactly like their segment.
 *
 * @param {object} viz_state - Visualization state.
 * @param {number} row_index - Raw row index.
 * @returns {number[]} [x, y] position.
 */
export const composition_row_label_position = (viz_state, row_index) => {
  const layout = get_composition_layout(viz_state);
  const leftmost_col = leftmost_composition_col(viz_state);
  const seg = layout[`${row_index}_${leftmost_col}`];
  const row_label_x_offset = 50; // matches the heatmap row-label left margin
  return [row_label_x_offset, seg ? seg.position[1] : 0];
};

/**
 * Recompute row-label fit/visibility and position for composition mode, and
 * re-trigger the row label layer's per-instance color + position accessors.
 * No-op outside composition mode. Call after any action that can change the
 * composition layout (row/col reorder, normalization toggle) as well as on
 * every `rows`-viewport zoom tick, since the fit check is zoom-dependent
 * there (see `compute_row_label_visibility`). Kept here (rather than
 * alongside the `TextLayer` in `label_layers.js`) so it has no dependency on
 * the UI button modules, which need to call it without introducing an import
 * cycle.
 *
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const refresh_row_label_visibility = (layers_mat, viz_state) => {
  if (viz_state.mat.viz_mode !== 'composition') return;

  viz_state.labels.row_visibility = compute_row_label_visibility(viz_state);
  viz_state.labels._row_vis_rev = (viz_state.labels._row_vis_rev || 0) + 1;

  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    visible: true,
    updateTriggers: {
      getColor: viz_state.labels._row_vis_rev,
      getPosition: viz_state.labels._row_vis_rev,
    },
  });

  // The bold focus overlay shares the base label's color/position accessors.
  // Cloning with a fresh copy of its (one-datum) data forces re-evaluation
  // without importing label_layers (which imports this module).
  if (layers_mat.row_label_focus_layer) {
    layers_mat.row_label_focus_layer = layers_mat.row_label_focus_layer.clone({
      data: [...(layers_mat.row_label_focus_layer.props.data || [])],
    });
  }
};
