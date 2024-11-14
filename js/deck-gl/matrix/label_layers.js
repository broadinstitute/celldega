import { TextLayer } from "deck.gl"

const row_label_get_position = (d, index, viz_state) => {

    const inst_index = index.index
    const inst_order = viz_state.order.current

    let index_offset
    if (inst_order === 'ini') {
        index_offset = 0
    } else {
        index_offset = 1
    }

    let inst_row_index = viz_state.mat.num_rows - viz_state.mat.row_orders[inst_order][inst_index] - index_offset

    const row_offset = 25

    let pos_x = row_offset
    let pos_y = viz_state.viz.row_offset * (inst_row_index + 1.5)

    const position = [pos_x, pos_y]

    return position

}

const col_label_get_position = (d, index, viz_state) => {

    const inst_index = index.index
    const inst_order = 'rank' // viz_state.order.current

    let index_offset
    if (inst_order === 'ini') {
        index_offset = 0
    } else {
        index_offset = 1
    }

    let inst_col_index = viz_state.mat.num_cols - viz_state.mat.col_orders[inst_order][inst_index] - index_offset

    const col_offset = 55

    let pos_x = viz_state.viz.col_offset * (inst_col_index + 0.5)
    let pos_y = col_offset

    const position = [pos_x, pos_y]

    return position

}

export const ini_row_label_layer = (viz_state) => {

    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: viz_state.labels.row_label_data,
        getPosition: (d, index) => row_label_get_position(d, index, viz_state),
        getText: d => d.name,
        getSize: viz_state.viz.inst_font_size,
        getColor: [0, 0, 0],
        getAngle: 0,
        getTextAnchor: 'end',
        getAlignmentBaseline: 'center',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        sizeScale: 2,
        // updateTriggers: {
        //   getSize: viz_state.viz.inst_font_size
        // },
        pickable: true,
    })

    return row_label_layer
}

export const ini_col_label_layer = (viz_state) => {

    const col_label_layer  = new TextLayer({
        id: 'col-label-layer',
        data: viz_state.labels.col_label_data,
        // getPosition: d => d.position,
        getPosition: (d, index) => col_label_get_position(d, index, viz_state),
        getText: d => d.name,
        getSize: viz_state.viz.inst_font_size,
        getColor: [0, 0, 0],
        getAngle: 45, // Optional: Text angle in degrees
        getTextAnchor: 'start', // middle
        getAlignmentBaseline: 'bottom',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        sizeScale: 2,
        // updateTriggers: {
        //   getSize: viz_state.viz.inst_font_size
        // },
        pickable: true,
    })

    return col_label_layer

}