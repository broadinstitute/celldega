export const set_row_cat_data = (network, viz_state) => {
  let index_row = 0;
  let matrix_index = 0;

  const num_points = viz_state.mat.num_rows * viz_state.cats.num_cats.row;

  const row_cat_data = new Array(num_points).fill(0).map(() => {
    const index_col = matrix_index % viz_state.cats.num_cats.row;

    if (matrix_index % viz_state.cats.num_cats.row === 0) {
      index_row += 1;
    }

    const p = {
      position: [
        // viz_state.viz.row_cat_offset * (index_col + 0.5),
        viz_state.viz.row_cat_offset * (index_col + 0.5) + 20,
        viz_state.viz.row_offset * (index_row + 0.5),
      ],
      color: [0, 255, 0, 255],
      name: `something ${index_row}`,
    };

    matrix_index += 1;

    return p;
  });

  return row_cat_data;
};

const hexToRgba = (hex, alpha = 255) => {
  const bigint = parseInt(hex.slice(1), 16);
  return [
    (bigint >> 16) & 255,
    (bigint >> 8) & 255,
    bigint & 255,
    alpha
  ];
};

export const set_col_cat_data = (network, viz_state) => {

  let index_row = 0;
  let matrix_index = 0;

  const col_cat_data = network.col_nodes.map((node, index_col) => {

    if (matrix_index % viz_state.mat.num_cols === 0) {
      index_row += 1;
    }

    // Get the cat-0 info for this node
    const ini_cat = node['cat-0']; // e.g., 'type: low'

    // Parse the type if needed (remove 'type: ' prefix)
    const clean_cat = ini_cat.split(': ')[1];

    // Get the color from network.cat_colors.col
    const color_hex = network.cat_colors.col['cat-0'][ini_cat];

    // Convert hex to rgba
    const color_rgba = hexToRgba(color_hex, 150); // helper function below

    const p = {
      position: [
        viz_state.viz.col_offset * (index_col + 0.5),
        // move cats down
        viz_state.viz.col_cat_offset * (index_row + 1.5) - 30,
      ],
      color: color_rgba,
      name: clean_cat
    };

    matrix_index += 1;

    return p;
  });

  return col_cat_data;
};

