import * as d3 from 'd3'

export const get_tooltip = (viz_state, params) => {

    const {object, layer} = params;

    d3.selectAll('.deck-tooltip')
      .style('margin-top', '75px')

    if (object) {
      // Check which layer the tooltip is currently over
      if (layer.id === 'row-label-layer') {
        // Display the row label when hovering over the row_label_layer
        return {
          html: `Row Label: ${object.name}`,
          style: {color: "white"},
        };
      }
      else if (layer.id === 'col-label-layer') {
        // Display the row label when hovering over the row_label_layer
        return {
          html: `Col Label: ${object.name}`,
          style: {color: "white"},
        };
      }
      else if (layer.id === 'row-layer') {
        // Display the row label when hovering over the row_label_layer
        return {
          html: `Row Label: ${object.name}`,
          style: {color: "white"},
        };
      }
      else if (layer.id === 'col-layer') {
        // Display the row label when hovering over the row_label_layer
        return {
          html: `Col Label: ${object.name}`,
          style: {color: "white"},
        };
      }
      else if (layer.id === 'mat-layer') {
        // Display the default tooltip for other layers

        const row_name = viz_state.labels.row_label_data[object.row].name;
        const col_name = viz_state.labels.col_label_data[object.col].name;

        return {
          html: `Row: ${row_name} <br> Column: ${col_name} <br> Value: ${object.value.toFixed(2)}`,
          style: {color: "white"},
        };
      }
    }
  }