export const get_tooltip = ({object, layer}) => {

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
        return {
          html: `Row: ${object.row} <br> Column: ${object.col}`,
          style: {color: "white"},
        };
      }
    }
  }