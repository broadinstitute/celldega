import { TextLayer } from "deck.gl"

export const ini_row_label_layer = (viz_state) => {

    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: viz_state.labels.row_label_data,
        getPosition: d => d.position,
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
        getPosition: d => d.position,
        getText: d => d.name,
        getSize: viz_state.viz.inst_font_size,
        getColor: [0, 0, 0],
        getAngle: 45, // Optional: Text angle in degrees
        getTextAnchor: 'start', // middle
        getAlignmentBaseline: 'bottom',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        updateTriggers: {
          getSize: viz_state.viz.inst_font_size
        },
        pickable: true,
    })

    return col_label_layer

    }