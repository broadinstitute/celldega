import { TextLayer } from "deck.gl"

export const ini_row_label_layer = (viz_state) => {

    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: viz_state.labels.row_label_data,
        getPosition: d => d.position,
        getText: d => d.name,
        getSize: d => viz_state.viz.inst_font_size,
        getColor: [0, 0, 0],
        getAngle: 0,
        getTextAnchor: 'end',
        getAlignmentBaseline: 'center',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        updateTriggers: {
          getSize: viz_state.viz.inst_font_size
        },
        pickable: true,
      })

    return row_label_layer
}