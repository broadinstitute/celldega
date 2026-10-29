// Matrix cell data + value encoding.
//
// Each matrix cell is one deck.gl instance. Two channels are available:
//   - color + opacity (alpha), and
//   - square/dot size (via the per-instance radius attribute; see mat_shaders.js).
//
// `viz_mode` decides how the main matrix value (and the optional secondary
// `size_mat`) map onto those channels:
//   - "heatmap": opacity ~ |value|, full-size squares (classic Clustergram).
//   - "dotplot": opacity ~ |value| (e.g. mean expression) and square/dot size ~
//                the secondary matrix (e.g. fraction of cells expressing).

/**
 * Resolve the requested viz mode, downgrading "dotplot" to "heatmap" when no
 * secondary size matrix is available.
 *
 * @param {string} mode - Requested mode.
 * @param {boolean} has_size_mat - Whether a secondary size matrix was provided.
 * @returns {string} A valid, renderable mode.
 */
export const resolve_viz_mode = (mode, has_size_mat) => {
  const requested = mode || 'heatmap';
  if (requested === 'dotplot' && !has_size_mat) return 'heatmap';
  if (!['heatmap', 'dotplot', 'composition'].includes(requested))
    return 'heatmap';
  return requested;
};

const encode_point = (p, viz_state) => {
  const { max_abs_value, max_size_value, viz_mode, dot_size_encoded } =
    viz_state.mat;
  const magnitude = Math.min(1, Math.abs(p.value) / max_abs_value);

  let alpha;
  let size_scale;

  if (viz_mode === 'dotplot') {
    alpha = magnitude;
    if (dot_size_encoded === false) {
      // DOT toggle off: full-tile square, like heatmap.
      size_scale = 1;
    } else {
      // Fractions ([0, 1]) stay absolute so a full square == 100%; count-like
      // matrices (max > 1) get normalized to their own maximum.
      const denom = max_size_value > 1 ? max_size_value : 1;
      size_scale = Math.max(0, Math.min(1, p.size_value / denom));
    }
  } else {
    alpha = magnitude;
    size_scale = 1;
  }

  p.color = [p.rgb[0], p.rgb[1], p.rgb[2], Math.round(255 * alpha)];
  p.size_scale = size_scale;
};

/**
 * Re-encode every existing matrix point in place from the current `viz_mode`.
 * Used when the mode changes at runtime so deck.gl can animate the transition.
 *
 * @param {object} viz_state - Visualization state.
 */
export const apply_mat_encoding = (viz_state) => {
  for (const p of viz_state.mat.mat_data) {
    encode_point(p, viz_state);
  }
};

export const set_mat_data = (network, viz_state) => {
  const { mat, size_mat } = network;
  const { col_offset, row_offset } = viz_state.viz;
  const { mat_data } = viz_state.mat;

  for (let index_row = 0; index_row < mat.length; index_row++) {
    const rowArray = mat[index_row];
    const sizeRow = size_mat ? size_mat[index_row] : null;

    for (let index_col = 0; index_col < rowArray.length; index_col++) {
      const tile_value = rowArray[index_col];

      // Optional: skip small/zero values to reduce memory
      if (tile_value == null || Math.abs(tile_value) < 1e-6) continue;

      const inst_color = tile_value >= 0 ? [255, 0, 0] : [0, 0, 255];
      const size_value = sizeRow != null ? sizeRow[index_col] || 0 : 0;

      const p = {
        position: [
          col_offset * (index_col + 0.5),
          row_offset * (index_row + 1.5),
        ],
        rgb: inst_color,
        value: tile_value,
        size_value,
        row: index_row,
        col: index_col,
      };

      encode_point(p, viz_state);

      mat_data.push(p);
    }
  }
};
