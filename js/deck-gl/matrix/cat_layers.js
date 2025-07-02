import * as d3 from 'd3';

import { CustomMatrixLayer } from './custom_matrix_layer';

export const ini_row_cat_layer = (viz_state) => {

  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const row_cat_layer = new CustomMatrixLayer({
    id: 'row-layer',
    data: viz_state.cats.row_cat_data,
    getPosition: (d) => {
      const row_order = viz_state.mat.orders.row[viz_state.order.current.row];

      // Use original_index to look up its rank
      const clustered_index =
        viz_state.mat.num_rows - row_order[d.original_index];

      return [
        d.position[0] + viz_state.viz.cat_shift_row,
        viz_state.viz.row_offset * (clustered_index + 1.5),
      ];
    },
    getFillColor: (d) => d.color,
    pickable: true,
    transitions,
    opacity: 0.8,
    tile_width: (viz_state.viz.row_cat_width / 2) * 0.9,
    tile_height: (viz_state.viz.mat_height / viz_state.mat.num_rows) * 0.5,
  });

  return row_cat_layer;
};

export const ini_col_cat_layer = (viz_state) => {
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const col_cat_layer = new CustomMatrixLayer({
    id: 'col-layer',
    data: viz_state.cats.col_cat_data,
    getPosition: (d) => {
      const col_order = viz_state.mat.orders.col[viz_state.order.current.col];

      // Use original_index to look up its rank
      const clustered_index =
        viz_state.mat.num_cols - col_order[d.original_index];

      return [
        viz_state.viz.col_offset * (clustered_index + 0.5),
        d.position[1] + viz_state.viz.cat_shift_col,
      ];
    },
    getFillColor: (d) => d.color,
    pickable: true,
    transitions,
    opacity: 0.8,
    tile_width: (viz_state.viz.mat_width / viz_state.mat.num_cols) * 0.5,
    tile_height: viz_state.viz.col_cat_height / 2,
  });

  return col_cat_layer;
};
