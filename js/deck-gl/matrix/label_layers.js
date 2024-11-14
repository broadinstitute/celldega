import { TextLayer } from "deck.gl"
import * as d3 from 'd3'

const row_label_get_position = (d, index, viz_state) => {

    const inst_index = index.index
    const inst_order = viz_state.order.current
    const row_offset = 25

    let index_offset
    if (inst_order === 'ini') {
        index_offset = 0
    } else {
        index_offset = 1
    }

    let inst_row_index = viz_state.mat.num_rows - viz_state.mat.row_orders[inst_order][inst_index] - index_offset


    let pos_x = row_offset
    let pos_y = viz_state.viz.row_offset * (inst_row_index + 1.5)

    const position = [pos_x, pos_y]

    return position

}

const col_label_get_position = (d, index, viz_state) => {

    const inst_index = index.index
    const inst_order = viz_state.order.current
    const col_offset = 50

    let index_offset
    if (inst_order === 'ini') {
        index_offset = 0
    } else {
        index_offset = 1
    }

    let inst_col_index = viz_state.mat.num_cols - viz_state.mat.col_orders[inst_order][inst_index] - index_offset

    let pos_x = viz_state.viz.col_offset * (inst_col_index + 0.5)
    let pos_y = col_offset // * zoom_factor

    const position = [pos_x, pos_y]

    return position

}

export const ini_row_label_layer = (viz_state) => {

    const transitions = {
        getPosition: {
            duration: viz_state.animate.duration,
            easing: d3.easeCubic
        }
    }

    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: viz_state.labels.row_label_data,
        getPosition: (d, index) => row_label_get_position(d, index, viz_state),
        getText: d => d.name,
        getSize: viz_state.viz.font_size.rows,
        getColor: [0, 0, 0],
        getAngle: 0,
        getTextAnchor: 'end',
        getAlignmentBaseline: 'center',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        sizeScale: 2,
        // updateTriggers: {
        //   getSize: viz_state.viz.ini_font_size,
        // },
        pickable: true,
        transitions: transitions,
    })

    return row_label_layer
}

export const ini_col_label_layer = (viz_state) => {

    // Define zoom-dependent offset
    function getPixelOffset(zoom_x, num_cols) {

        const zoom_factor = Math.pow(2, zoom_x)
        const offset_y = 75 / num_cols
        const scaled_offset_y = offset_y * zoom_factor

        return [0, scaled_offset_y];
    }

    const transitions = {
        getPosition: {
            duration: viz_state.animate.duration,
            easing: d3.easeCubic
        }
    }

    const col_label_layer  = new TextLayer({
        id: 'col-label-layer',
        data: viz_state.labels.col_label_data,
        getPosition: (d, index) => col_label_get_position(d, index, viz_state),
        getText: d => d.name,
        getSize: viz_state.viz.font_size.cols,
        getColor: [0, 0, 0],
        getAngle: 45, // Optional: Text angle in degrees
        getTextAnchor: 'start', // middle
        getAlignmentBaseline: 'bottom',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        sizeScale: 2,
        // updateTriggers: {
        // //   getSize: viz_state.viz.ini_font_size,
        //   getPosition: viz_state.viz.font_size,
        //   getPixelOffset: viz_state.zoom.zoom_data.matrix.zoom_x,
        // },
        pickable: true,
        transitions: transitions,
        getPixelOffset: () => getPixelOffset(viz_state.zoom.zoom_data.matrix.zoom_x, viz_state.mat.num_cols),
    })

    return col_label_layer

}