import * as d3 from 'd3';

import { colorToRgba } from './cat_data';

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
  return `${row_key}|${col_key}|${normalized}|${weights_sig}|${row_arr.join(',')}|${col_arr.join(',')}`;
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
  const { num_rows, num_cols, net_mat, orders, composition_normalized } =
    viz_state.mat;
  const { mat_height, col_width, row_offset } = viz_state.viz;
  const row_order = orders.row[viz_state.order.current.row];
  const col_order = orders.col[viz_state.order.current.col];
  const normalized = composition_normalized;

  // Column sums (only non-negative contributions stack).
  const col_sums = new Array(num_cols).fill(0);
  for (let r = 0; r < num_rows; r++) {
    const row = net_mat[r];
    for (let c = 0; c < num_cols; c++) {
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
  const col_weights = Array.from({ length: num_cols }, (_, c) => {
    const name = viz_state.col_nodes[c]?.name;
    const explicit = name != null ? col_weights_by_name[name] : undefined;
    return explicit != null ? explicit : col_sums[c];
  });
  const max_weight = Math.max(...col_weights, 1e-9);

  const y_top = row_offset * 1.0; // top edge of the body region
  const half_width = col_width * 0.5 * 0.95; // small (5%) gap between bars

  // Stack rows in the SAME order across every bar (row identity always maps
  // to the same relative vertical band everywhere), driven by the shared
  // "POP:" row order. Ascending by row_order — so double-clicking a column
  // (which ranks the highest value as the largest row_order via the generic
  // custom_label_reorder) puts that column's largest population at the
  // bottom, matching the standard bar-chart "biggest at the base" look —
  // without making each bar sort independently by its own local values.
  const rows_sorted = Array.from({ length: num_rows }, (_, i) => i).sort(
    (a, b) => row_order[a] - row_order[b]
  );

  const layout = {};
  for (let c = 0; c < num_cols; c++) {
    const x_index = num_cols - col_order[c];
    const x_center = col_width * (x_index + 0.5);
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

/**
 * The currently-leftmost displayed column (smallest displayed x_index under
 * the current col order). Used both to decide which row labels fit and to
 * position them next to that bar.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {number} Raw column index.
 */
export const leftmost_composition_col = (viz_state) => {
  const { num_cols, orders } = viz_state.mat;
  const col_order = orders.col[viz_state.order.current.col];

  let leftmost_col = 0;
  let min_x_index = Infinity;
  for (let c = 0; c < num_cols; c++) {
    const x_index = num_cols - col_order[c];
    if (x_index < min_x_index) {
      min_x_index = x_index;
      leftmost_col = c;
    }
  }
  return leftmost_col;
};

// A row label is only hidden when its segment is degenerate (the population
// isn't present in that column at all) — labels are otherwise always shown,
// however small, since zooming in on the `rows` viewport makes them legible
// again in absolute screen-pixel terms (both the segment and its zoom-scaled
// font grow together).
const MIN_SEGMENT_HEIGHT = 1e-6;

/**
 * Per-row visibility for population (row) labels in composition mode: hidden
 * only when the leftmost displayed bar has no segment (or a zero-height one)
 * for that row.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {boolean[]} Indexed by raw row index (matches `row_label_data[i].index`).
 */
export const compute_row_label_visibility = (viz_state) => {
  const { num_rows } = viz_state.mat;
  const layout = get_composition_layout(viz_state);
  const leftmost_col = leftmost_composition_col(viz_state);

  const visible = new Array(num_rows).fill(false);
  for (let r = 0; r < num_rows; r++) {
    const seg = layout[`${r}_${leftmost_col}`];
    visible[r] = !!seg && seg.half[1] * 2 >= MIN_SEGMENT_HEIGHT;
  }
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
 * composition layout: row/col reorder, normalization toggle. Kept here
 * (rather than alongside the `TextLayer` in `label_layers.js`) so it has no
 * dependency on the UI button modules, which need to call it without
 * introducing an import cycle.
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
};
