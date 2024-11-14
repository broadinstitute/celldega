import { CustomMatrixLayer } from "./custom_matrix_layer";
import * as d3 from 'd3'
import { get_layers_list } from "./matrix_layers";

const mat_layer_get_position = (d, viz_state) => {

    const inst_order_rows = viz_state.order.current.rows
    const inst_order_cols = viz_state.order.current.cols

    let index_offset
    if (inst_order_rows === 'ini') {
        index_offset = 0
    } else {
        index_offset = 1
    }

    let inst_row_index = viz_state.mat.num_cols - viz_state.mat.orders.col[inst_order_rows][d.col] - index_offset
    let inst_col_index = viz_state.mat.num_rows - viz_state.mat.orders.row[inst_order_cols][d.row] - index_offset

    let pos_x = viz_state.viz.col_width * (inst_row_index + 0.5)
    let pos_y = viz_state.viz.row_offset * (inst_col_index + 1.5)

    const position = [pos_x, pos_y]

    return position

}

export const ini_mat_layer = (viz_state) => {

    const transitions = {
        getPosition: {
            duration: viz_state.animate.duration,
            easing: d3.easeCubic
        }
    }

    const mat_layer = new CustomMatrixLayer({
        id: 'mat-layer',
        data: viz_state.mat.mat_data,
        getPosition: ( d ) => mat_layer_get_position(d, viz_state),
        getFillColor: d => d.color,
        pickable: true,
        antialiasing: false,
        tile_height: viz_state.viz.mat_height/viz_state.mat.num_rows * 0.5,
        tile_width: viz_state.viz.mat_height/viz_state.mat.num_cols * 0.5,
        transitions: transitions,
    })

    return mat_layer

}

const mat_layer_onclick = (deck_mat, layers_mat, viz_state) => {

    if (viz_state.order.current.rows === 'ini') {
        viz_state.order.current.rows = 'clust'
        viz_state.order.current.cols = 'clust'
    } else if (viz_state.order.current.rows === 'clust') {
        viz_state.order.current.rows = 'ini'
        viz_state.order.current.cols = 'ini'
    }

    layers_mat.mat_layer = layers_mat.mat_layer.clone({
        updateTriggers: {
            getPosition: [viz_state.order.current.rows, viz_state.order.current.cols]
        }
    })

    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        updateTriggers: {
            getPosition: viz_state.order.current.rows
        }
    })

    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        updateTriggers: {
            getPosition: viz_state.order.current.cols
        }
    })

    deck_mat.setProps({
        layers: get_layers_list(layers_mat),
    })
}

export const set_mat_layer_onclick = (deck_mat, layers_mat, viz_state) => {

    layers_mat.mat_layer = layers_mat.mat_layer.clone({
        // not using event or d
        onClick: () =>  mat_layer_onclick(deck_mat, layers_mat, viz_state)
    })

}