import {
  escape_html,
  gene_info_tooltip_html,
  is_gene_axis,
  refresh_gene_tooltip_async,
} from '../../ui/gene_info';

const DENDRO_TOOLTIP_OFFSET_PX = 8;
const DENDRO_TOOLTIP_EDGE_BUFFER_PX = 72;
const DENDRO_TOOLTIP_NAME_LIMIT = 12;

const dendro_names_html = (names) => {
  const list = Array.isArray(names) ? names : [];
  if (list.length === 0) return '';

  const shown = list.slice(0, DENDRO_TOOLTIP_NAME_LIMIT);
  const hidden_count = list.length - shown.length;
  const shown_html = shown.map((name) => escape_html(name)).join(', ');
  if (hidden_count <= 0) return shown_html;

  return `${shown_html}<br><i>+${hidden_count} more (${list.length} total)</i>`;
};

const dendro_tooltip_html = (label, object) => {
  const properties = object?.properties || {};
  const names_html = dendro_names_html(properties.all_names);
  const names_line = names_html ? `<br>${names_html}` : '';
  return `${label} dendrogram: ${escape_html(properties.name)}${names_line}`;
};

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

// The column attribute labels sit directly above the row dendrogram (see
// views.js: `col_attr_labels` shares its x range with `dendro_rows`), so their
// tooltip opens leftward over the matrix instead of down over the dendrogram.
const ATTR_TOOLTIP_OFFSET_PX = 8;

const attr_tooltip_style = () => ({
  ...base_tooltip_style(),
  translate: `calc(-100% - ${ATTR_TOOLTIP_OFFSET_PX}px) ${ATTR_TOOLTIP_OFFSET_PX}px`,
});

// Dendrogram tooltips open back over the matrix rather than outward over the
// dendrogram itself, so the trapezoids the user is reading stay visible. The
// row dendrogram sits to the right of the matrix (open leftward); the column
// dendrogram sits below it (open upward), unless that would run off the top.
const dendro_tooltip_style = (viz_state, params, axis) => {
  const y = params?.y ?? 0;
  const near_top = y < DENDRO_TOOLTIP_EDGE_BUFFER_PX;
  const offset = `${DENDRO_TOOLTIP_OFFSET_PX}px`;

  if (axis === 'row') {
    return {
      ...base_tooltip_style(),
      translate: `calc(-100% - ${offset}) ${offset}`,
    };
  }

  return {
    ...base_tooltip_style(),
    translate: near_top
      ? `${offset} ${offset}`
      : `${offset} calc(-100% - ${offset})`,
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
  const { object, layer } = params || {};
  const layer_id = layer?.id || '';

  reset_tooltip_position(viz_state);

  if (viz_state.crop?.drag) {
    hide_tooltip(viz_state);
    return null;
  }

  if (object) {
    // Check which layer the tooltip is currently over
    // `includes` also matches the bold focus overlay ('row-label-layer-focus'),
    // which replaces the base label for the focused row.
    if (layer_id.includes('row-label-layer')) {
      const row_name = object.name;
      const build_html = () =>
        `Row Label: ${escape_html(
          object.display_name || object.name
        )}${is_gene_axis(viz_state, 'row') ? gene_info_tooltip_html(row_name) : ''}`;

      // Gene rows carry a UniProt name/description; the first hover renders a
      // placeholder and this patches it in when the lookup resolves.
      if (is_gene_axis(viz_state, 'row')) {
        refresh_gene_tooltip_async(viz_state.root, row_name, build_html);
      }

      return {
        html: build_html(),
        style: base_tooltip_style(),
      };
    } else if (layer_id === 'col-label-layer') {
      return {
        html: `Col Label: ${escape_html(object.display_name || object.name)}`,
        style: base_tooltip_style(),
      };
    } else if (layer_id === 'row-layer') {
      const row_attr_name = viz_state.attr.names.row[object.level];
      return {
        html: `${escape_html(row_attr_name)}: ${escape_html(object.name)}`,
        style: base_tooltip_style(),
      };
    } else if (layer_id === 'col-layer') {
      const col_attr_name = viz_state.attr.names.col[object.level];
      return {
        html: `${escape_html(col_attr_name)}: ${escape_html(object.name)}`,
        style: base_tooltip_style(),
      };
    } else if (layer_id === 'row-dendro-layer') {
      return {
        html: dendro_tooltip_html('Row', object),
        style: dendro_tooltip_style(viz_state, params, 'row'),
      };
    } else if (layer_id === 'col-dendro-layer') {
      return {
        html: dendro_tooltip_html('Column', object),
        style: dendro_tooltip_style(viz_state, params, 'col'),
      };
    } else if (layer_id.includes('mat-layer')) {
      // Display the default tooltip for other layers

      const row_entry = viz_state.labels.row_label_data[object.row];
      const col_entry = viz_state.labels.col_label_data[object.col];
      const row_name = escape_html(row_entry?.display_name || row_entry?.name);
      const col_name = escape_html(col_entry?.display_name || col_entry?.name);

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
    } else if (layer_id === 'row-attr-label-layer') {
      return {
        html: `Row Attribute: ${escape_html(
          object.name
        )}<br><i>Double-click to reorder by this attribute</i>`,
        style: base_tooltip_style(),
      };
    } else if (layer_id === 'col-attr-label-layer') {
      return {
        html: `Column Attribute: ${escape_html(
          object.name
        )}<br><i>Double-click to reorder by this attribute</i>`,
        // This strip sits directly above the row dendrogram.
        style: attr_tooltip_style(),
      };
    }
  }
};
