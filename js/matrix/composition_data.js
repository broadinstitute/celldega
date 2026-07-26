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
  const half_width = col_width * 0.5 * 0.9; // small gap between bars

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
