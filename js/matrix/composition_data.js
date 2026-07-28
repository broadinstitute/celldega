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
  return `${row_key}|${col_key}|${normalized}|${row_arr.join(',')}|${col_arr.join(',')}`;
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
  const max_sum = Math.max(...col_sums, 1e-9);

  // Stack rows top -> bottom following the current row order (smaller y-slot
  // sits higher, matching the heatmap's `num_rows - rank` convention).
  const y_slot = (r) => num_rows - row_order[r];
  const rows_sorted = Array.from({ length: num_rows }, (_, i) => i).sort(
    (a, b) => y_slot(a) - y_slot(b)
  );

  const y_top = row_offset * 1.0; // top edge of the body region
  const half_width = col_width * 0.5 * 0.95; // small (5%) gap between bars

  const layout = {};
  for (let c = 0; c < num_cols; c++) {
    const x_index = num_cols - col_order[c];
    const x_center = col_width * (x_index + 0.5);
    const denom = normalized ? col_sums[c] || 1 : max_sum;

    let cursor = y_top;
    for (const r of rows_sorted) {
      const v = Math.max(0, net_mat[r][c] || 0);
      const seg_h = (v / denom) * mat_height;
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

// Minimum segment height, as a multiple of the row font size, for a row
// label to be considered "fits" (roughly one line of text tall).
const MIN_LABEL_HEIGHT_RATIO = 1.0;

/**
 * Per-row visibility for population (row) labels in composition mode, based
 * on whether the leftmost displayed bar's segment for that row is tall
 * enough to hold a line of text. Both the segment height and the row font
 * size are world-space quantities scaled identically by zoom in the `rows`
 * viewport, so the ratio test is zoom-invariant and only needs recomputing
 * when the layout itself changes (reorder, normalization) — not on every
 * pan/zoom tick.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {boolean[]} Indexed by raw row index (matches `row_label_data[i].index`).
 */
export const compute_row_label_visibility = (viz_state) => {
  const { num_rows } = viz_state.mat;
  const layout = get_composition_layout(viz_state);
  const leftmost_col = leftmost_composition_col(viz_state);

  const min_seg_h = viz_state.viz.font_size.rows * MIN_LABEL_HEIGHT_RATIO;
  const visible = new Array(num_rows).fill(false);
  for (let r = 0; r < num_rows; r++) {
    const seg = layout[`${r}_${leftmost_col}`];
    visible[r] = !!seg && seg.half[1] * 2 >= min_seg_h;
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
