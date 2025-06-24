import { CustomMatrixLayer } from './custom_matrix_layer';

export const ini_row_cat_layer = (viz_state) => {


  const row_cat_layer = new CustomMatrixLayer({
    id: 'row-layer',
    data: viz_state.cats.row_cat_data,
    getPosition: (d, index) => {
      const row_order = viz_state.mat.orders.row[viz_state.order.current.row];
      const inst_index = index.index;
      const inst_order_index =
        viz_state.mat.num_rows - row_order[inst_index];

      return [
        d.position[0] + viz_state.viz.cat_shift_row,
        viz_state.viz.row_offset * (inst_order_index + 0.5),
      ];
    },
    getFillColor: (d) => d.color,
    pickable: true,
    opacity: 0.8,
    tile_width: (viz_state.viz.row_cat_width / 2) * 0.9,
    tile_height: (viz_state.viz.mat_height / viz_state.mat.num_rows) * 0.5,
  });

  return row_cat_layer;
};

// export const ini_row_cat_layer = (viz_state) => {
//   const row_order = viz_state.mat.orders.row[viz_state.order.current.row];

//   const row_cat_layer = new CustomMatrixLayer({
//     id: 'row-layer',
//     data: viz_state.cats.row_cat_data,
//     getPosition: (d) => {
//       const clustered_index = row_order.indexOf(d.original_index);

//       return [
//         d.position[0] + viz_state.viz.cat_shift_row,
//         viz_state.viz.row_offset * (clustered_index + 0.5),
//       ];
//     },
//     getFillColor: (d) => d.color,
//     pickable: true,
//     opacity: 0.8,
//     tile_width: (viz_state.viz.row_cat_width / 2) * 0.9,
//     tile_height: (viz_state.viz.mat_height / viz_state.mat.num_rows) * 0.5,
//   });

//   return row_cat_layer;
// };


// export const ini_col_cat_layer = (viz_state) => {
//   const col_order = viz_state.mat.orders.col[viz_state.order.current.col];

//   const col_cat_layer = new CustomMatrixLayer({
//     id: 'col-layer',
//     data: viz_state.cats.col_cat_data,
//     getPosition: (d, index) => {
//       const inst_index = index.index;
//       const inst_order_index =
//         viz_state.mat.num_cols - col_order[inst_index];

//       return [
//         viz_state.viz.col_offset * (inst_order_index + 0.5),
//         d.position[1] + viz_state.viz.cat_shift_col,
//       ];
//     },
//     getFillColor: (d) => d.color,
//     pickable: true,
//     opacity: 0.8,
//     tile_width: (viz_state.viz.mat_height / viz_state.mat.num_cols) * 0.5,
//     tile_height: viz_state.viz.col_cat_height / 2,
//   });

//   return col_cat_layer;
// };

// export const ini_col_cat_layer = (viz_state) => {
//   const col_order = viz_state.mat.orders.col[viz_state.order.current.col];

//   const col_cat_layer = new CustomMatrixLayer({
//     id: 'col-layer',
//     data: viz_state.cats.col_cat_data,
//     getPosition: (d) => {
//       // We assume d.original_index is in your col_cat_data
//       const clustered_index = col_order.indexOf(d.original_index);

//       return [
//         viz_state.viz.col_offset * (clustered_index + 0.5),
//         d.position[1] + viz_state.viz.cat_shift_col,
//       ];
//     },
//     getFillColor: (d) => d.color,
//     pickable: true,
//     opacity: 0.8,
//     tile_width: (viz_state.viz.mat_height / viz_state.mat.num_cols) * 0.5,
//     tile_height: viz_state.viz.col_cat_height / 2,
//   });

//   return col_cat_layer;
// };

export const ini_col_cat_layer = (viz_state) => {

  const col_cat_layer = new CustomMatrixLayer({
    id: 'col-layer',
    data: viz_state.cats.col_cat_data,
    getPosition: (d) => {

      const col_order = viz_state.mat.orders.col[viz_state.order.current.col];
      console.log('ini_col_cat_layer: col_order', col_order);

      // Use original_index to look up its rank
      const clustered_index = viz_state.mat.num_cols - col_order[d.original_index];

      return [
        viz_state.viz.col_offset * (clustered_index + 0.5),
        d.position[1] + viz_state.viz.cat_shift_col,
      ];
    },
    getFillColor: (d) => d.color,
    pickable: true,
    opacity: 0.8,
    tile_width: (viz_state.viz.mat_height / viz_state.mat.num_cols) * 0.5,
    tile_height: viz_state.viz.col_cat_height / 2,
  });

  return col_cat_layer;
};

