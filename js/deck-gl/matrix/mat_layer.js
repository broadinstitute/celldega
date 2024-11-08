import { CustomMatrixLayer } from "./custom_matrix_layer";

export const ini_mat_layer = (viz_state) => {

    const mat_layer = new CustomMatrixLayer({
        id: 'mat-layer',
        data: viz_state.mat.mat_data,
        getPosition: d => d.position,
        getFillColor: d => d.color,
        pickable: true,
        opacity: 0.8,
        antialiasing: false,
        tile_height: viz_state.viz.mat_height/viz_state.mat.num_rows * 0.5,
        tile_width: viz_state.viz.mat_height/viz_state.mat.num_cols * 0.5

    })

    return mat_layer

}