import { CustomMatrixLayer } from "./custom_matrix_layer";
import * as d3 from 'd3'
import { get_layers_list } from "./matrix_layers";

// animation transition function
// https://observablehq.com/@cornhundred/deck-gl-instanced-scatter-test
const transitions = {
    opacity: {
        duration: 500,
        easing: d3.easeCubic
    },
    getPosition: {
        duration: 1000,
        easing: d3.easeCubic
    }
}

const mat_layer_get_position = (d, viz_state) => {

    const inst_order = 'ini'

    let index_offset
    if (inst_order === 'ini') {
        index_offset = 0
    } else if (inst_order === 'clust') {
        index_offset = 1
    }

    // let inst_row_index = d.col
    let inst_row_index = viz_state.labels.col_label_data.length - viz_state.labels.col_label_data[d.col][inst_order] - index_offset

    // let inst_col_index = d.row
    let inst_col_index = viz_state.labels.row_label_data.length - viz_state.labels.row_label_data[d.row][inst_order] - index_offset



    console.log()

    let pos_x = viz_state.viz.col_width * (inst_row_index + 0.5)
    let pos_y = viz_state.viz.row_offset * (inst_col_index + 1.5)

    const position = [pos_x, pos_y]

    return position

}

export const ini_mat_layer = (viz_state) => {


    const mat_layer = new CustomMatrixLayer({
        id: 'mat-layer',
        data: viz_state.mat.mat_data,
        getPosition: ( d ) => mat_layer_get_position(d, viz_state),
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

const mat_layer_onclick = (event, d, deck_mat, layers_mat, viz_state) => {

    console.log('here!!!!!!!!!!!')
    console.log(event, d)

    console.log(viz_state.mat.mat_data)

    layers_mat.mat_layer = layers_mat.mat_layer.clone({
        opacity: 0.5,
        getPosition: d => [d.position[1], d.position[0]],
        updateTriggers: {
            getPosition: event // Math.random() // Change to force re-evaluation
        }
    })

    deck_mat.setProps({
        layers: get_layers_list(layers_mat),
    })
}

export const set_mat_layer_onclick = (deck_mat, layers_mat, viz_state) => {

    console.log('set_mat_layer_onclick')

    layers_mat.mat_layer = layers_mat.mat_layer.clone({
        onClick: (event, d) =>  mat_layer_onclick(event, d, deck_mat, layers_mat, viz_state)
    })

}