const DENDRO_TOOLTIP_OFFSET_PX = 8;
const DENDRO_TOOLTIP_EDGE_BUFFER_PX = 72;

const base_tooltip_style = () => ({
  color: 'white',
  display: 'block',
  marginLeft: '0px',
  marginTop: '0px',
  translate: '0 0',
});

const reset_tooltip_position = (viz_state) => {
  const tooltip_container = viz_state.root?.querySelector?.('.deck-tooltip');
  if (!tooltip_container) return;

  tooltip_container.style.marginLeft = '0px';
  tooltip_container.style.marginTop = '0px';
  tooltip_container.style.translate = '0 0';

  const tooltip_parent = tooltip_container.parentElement?.parentElement;
  if (tooltip_parent) {
    tooltip_parent.style.position = 'unset';
  }
};

const dendro_tooltip_style = (viz_state, params, preferred_side) => {
  const y = params?.y ?? 0;
  const root_height = viz_state.root?.clientHeight || 0;
  const near_top = y < DENDRO_TOOLTIP_EDGE_BUFFER_PX;
  const near_bottom =
    root_height > 0 && y > root_height - DENDRO_TOOLTIP_EDGE_BUFFER_PX;
  const use_above =
    preferred_side === 'above' ? !near_top : Boolean(near_bottom);
  const offset = `${DENDRO_TOOLTIP_OFFSET_PX}px`;

  return {
    ...base_tooltip_style(),
    translate: use_above
      ? `${offset} calc(-100% - ${offset})`
      : `${offset} ${offset}`,
  };
};

export const hide_tooltip = (viz_state) => {
  const tooltip_container = viz_state.root?.querySelector?.('.deck-tooltip');
  if (!tooltip_container) return;

  reset_tooltip_position(viz_state);
  tooltip_container.innerHTML = '';
  tooltip_container.style.display = 'none';
};

export const get_tooltip = (viz_state, params) => {
  const { object, layer } = params;

  reset_tooltip_position(viz_state);

  if (viz_state.crop?.drag) {
    hide_tooltip(viz_state);
    return null;
  }

  if (object) {
    // Check which layer the tooltip is currently over
    if (layer.id === 'row-label-layer') {
      return {
        html: `Row Label: ${object.display_name || object.name}`,
        style: base_tooltip_style(),
      };
    } else if (layer.id === 'col-label-layer') {
      return {
        html: `Col Label: ${object.display_name || object.name}`,
        style: base_tooltip_style(),
      };
    } else if (layer.id === 'row-layer') {
      const row_attr_name = viz_state.attr.names.row[object.level];
      return {
        html: `${row_attr_name}: ${object.name}`,
        style: base_tooltip_style(),
      };
    } else if (layer.id === 'col-layer') {
      const col_attr_name = viz_state.attr.names.col[object.level];
      return {
        html: `${col_attr_name}: ${object.name}`,
        style: base_tooltip_style(),
      };
    } else if (layer.id === 'row-dendro-layer') {
      return {
        html: `Row dendrogram: ${object.properties.name}<br>${object.properties.all_names}`,
        style: dendro_tooltip_style(viz_state, params, 'below'),
      };
    } else if (layer.id === 'col-dendro-layer') {
      return {
        html: `Column dendrogram: ${object.properties.name}<br>${object.properties.all_names}`,
        style: dendro_tooltip_style(viz_state, params, 'above'),
      };
    } else if (layer.id.includes('mat-layer')) {
      // Display the default tooltip for other layers

      const row_entry = viz_state.labels.row_label_data[object.row];
      const col_entry = viz_state.labels.col_label_data[object.col];
      const row_name = row_entry?.display_name || row_entry?.name;
      const col_name = col_entry?.display_name || col_entry?.name;

      // Mode-specific secondary lines: dotplot surfaces the size channel;
      // composition labels the axes as population / dataset and surfaces the
      // dataset's total cell count alongside this cell's value.
      if (viz_state.mat.viz_mode === 'composition') {
        const col_node_name = viz_state.col_nodes?.[object.col]?.name;
        const weights = viz_state.mat.composition_col_weights || {};
        const explicit_total =
          col_node_name != null ? weights[col_node_name] : undefined;
        const total = explicit_total != null ? explicit_total : object.col_sum;
        const total_line =
          total != null ? `<br>Total cells: ${Math.round(total)}` : '';

        return {
          html: `Population: ${row_name}<br>Dataset: ${col_name}<br>Value: ${object.value.toFixed(
            2
          )}${total_line}`,
          style: base_tooltip_style(),
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
        style: base_tooltip_style(),
      };
    } else if (layer.id === 'row-attr-label-layer') {
      return {
        html: `Row Attribute: ${object.name}<br><i>Double-click to reorder by this attribute</i>`,
        style: base_tooltip_style(),
      };
    } else if (layer.id === 'col-attr-label-layer') {
      return {
        html: `Column Attribute: ${object.name}<br><i>Double-click to reorder by this attribute</i>`,
        style: base_tooltip_style(),
      };
    }
  }
};
