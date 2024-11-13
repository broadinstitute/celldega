import { CustomMatrixLayer } from "./custom_matrix_layer";
import * as d3 from 'd3'

export const ini_mat_layer = (viz_state) => {

    // animation transition function
    // https://observablehq.com/@cornhundred/deck-gl-instanced-scatter-test
    const transitions = ({
        opacity: {
          duration: 500,
          easing: d3.easeCubic
        },
        getPosition: {
          duration: 500,
          easing: d3.easeCubic
        }
    })

    const mat_layer = new CustomMatrixLayer({
        id: 'mat-layer',
        data: viz_state.mat.mat_data,
        getPosition: d => [d.position[0], d.position[1]],
        // getPosition: d => [10, 10],
        getFillColor: d => d.color,
        pickable: true,
        // opacity: 0.8,
        antialiasing: false,
        tile_height: viz_state.viz.mat_height/viz_state.mat.num_rows * 0.5,
        tile_width: viz_state.viz.mat_height/viz_state.mat.num_cols * 0.5,
        transitions: transitions,
        // onClick: (event, d) => {
        //     console.log(event, d)
        // }

    })

    return mat_layer

}