export const get_tooltip = (viz_state, params) => {
  const { object, layer } = params;

  // select the parent element of .deck-tooltip within viz_state.root
  const tooltipContainer = viz_state.root.querySelector('.deck-tooltip');
  tooltipContainer.style.marginTop = '50px';
  const tooltipParent = tooltipContainer.parentElement.parentElement;
  tooltipParent.style.position = 'unset';

  if (object) {
    // Check which layer the tooltip is currently over
    if (layer.id === 'row-label-layer') {
      return {
        html: `Row Label: ${object.display_name || object.name}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'col-label-layer') {
      return {
        html: `Col Label: ${object.display_name || object.name}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'row-layer') {
      const row_attr_name = viz_state.attr.names.row[object.level];
      return {
        html: `${row_attr_name}: ${object.name}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'col-layer') {
      const col_attr_name = viz_state.attr.names.col[object.level];
      return {
        html: `${col_attr_name}: ${object.name}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'row-dendro-layer') {
      return {
        html: `row-dendro-${object.properties.name}<br>${object.properties.all_names}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'col-dendro-layer') {
      return {
        html: `row-dendro-${object.properties.name}<br>${object.properties.all_names}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'mat-layer') {
      // Display the default tooltip for other layers

      const row_entry = viz_state.labels.row_label_data[object.row];
      const col_entry = viz_state.labels.col_label_data[object.col];
      const row_name = row_entry?.display_name || row_entry?.name;
      const col_name = col_entry?.display_name || col_entry?.name;

      // Mode-specific secondary lines: dotplot surfaces the size channel;
      // composition labels the axes as population / dataset.
      if (viz_state.mat.viz_mode === 'composition') {
        return {
          html: `Population: ${row_name}<br>Dataset: ${col_name}<br>Value: ${object.value.toFixed(
            2
          )}`,
          style: { color: 'white' },
        };
      }

      const size_line =
        viz_state.mat.viz_mode === 'dotplot' && object.size_value != null
          ? `<br> Size: ${object.size_value.toFixed(2)}`
          : '';

      return {
        html: `Row: ${row_name} <br> Column: ${col_name} <br> Value: ${object.value.toFixed(
          2
        )}${size_line}`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'row-attr-label-layer') {
      return {
        html: `Row Attribute: ${object.name}<br><i>Double-click to reorder by this attribute</i>`,
        style: { color: 'white' },
      };
    } else if (layer.id === 'col-attr-label-layer') {
      return {
        html: `Column Attribute: ${object.name}<br><i>Double-click to reorder by this attribute</i>`,
        style: { color: 'white' },
      };
    }
  }
};
