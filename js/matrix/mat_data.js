export const set_mat_data = (network, viz_state) => {
  const { mat } = network;
  const { col_offset, row_offset } = viz_state.viz;
  const max_abs_value = viz_state.mat.max_abs_value;
  const mat_data = viz_state.mat.mat_data;

  for (let index_row = 0; index_row < mat.length; index_row++) {
    const rowArray = mat[index_row];

    for (let index_col = 0; index_col < rowArray.length; index_col++) {
      const tile_value = rowArray[index_col];

      // Optional: skip small/zero values to reduce memory
      if (tile_value == null || Math.abs(tile_value) < 1e-6) continue;

      const inst_color = tile_value >= 0 ? [255, 0, 0] : [0, 0, 255];

      const p = {
        position: [
          col_offset * (index_col + 0.5),
          row_offset * (index_row + 1.5),
        ],
        color: [
          inst_color[0],
          inst_color[1],
          inst_color[2],
          (255 * Math.abs(tile_value)) / max_abs_value,
        ],
        value: tile_value,
        row: index_row,
        col: index_col,
      };

      mat_data.push(p);
    }
  }
};
