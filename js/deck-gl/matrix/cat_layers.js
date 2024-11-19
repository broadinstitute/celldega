import { CustomMatrixLayer } from "./custom_matrix_layer";

export const ini_row_cat_layer = (viz_state) => {

    // Create a new ScatterplotLayer using the input data
    const row_cat_layer = new CustomMatrixLayer({
        id: 'row-layer',
        data: viz_state.cats.row_cat_data,
        getPosition: d => [d.position[0] + viz_state.viz.cat_shift_row, d.position[1]],
        getFillColor: d => d.color,
        pickable: true,
        opacity: 0.8,
        tile_width: viz_state.viz.row_cat_width/2 * 0.9,
        tile_height: viz_state.viz.mat_height/viz_state.mat.num_rows * 0.5,
    });

    return row_cat_layer
}

export const ini_col_cat_layer = (viz_state) => {

    const col_cat_layer = new CustomMatrixLayer({
        id: 'col-layer',
        data: viz_state.cats.col_cat_data,
        getPosition: d => [d.position[0], d.position[1] + viz_state.viz.cat_shift_col],
        getFillColor: d => d.color,
        pickable: true,
        opacity: 0.8,
        tile_width: viz_state.viz.mat_height/viz_state.mat.num_cols * 0.5 ,
        tile_height: viz_state.viz.col_cat_height/2,

    })

    return col_cat_layer
}
