import * as d3 from 'd3-color';

import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers';
import { ini_views, ini_view_state } from '../deck-gl/matrix/views';

import { colorToRgba } from './cat_data';

const FALLBACK_COLORS = [
  '#1f77b4',
  '#ff7f0e',
  '#2ca02c',
  '#d62728',
  '#9467bd',
  '#8c564b',
  '#e377c2',
  '#7f7f7f',
  '#bcbd22',
  '#17becf',
];

const MANUAL_FILL_VALUE = 'N.A.';
const MANUAL_FILL_COLOR = '#d1d5db';

const ensure_string = (value) =>
  value === null || value === undefined ? null : String(value);

const normalize_axis = (axis) => (axis === 'col' ? 'col' : 'row');

const fallback_color = (value, index) => {
  const palette_color = FALLBACK_COLORS[index % FALLBACK_COLORS.length];
  if (typeof value === 'string') {
    const col = d3.color(value);
    if (col) return value;
  }
  return palette_color;
};

const compute_geometry = (viz_state) => {
  const total_row_attrs = viz_state.attr.num.row;
  const total_col_attrs = viz_state.attr.num.col;

  viz_state.viz.mat_width =
    viz_state.viz.total_width - viz_state.viz.row_cat_offset * total_row_attrs;
  viz_state.viz.mat_height =
    viz_state.viz.total_height - viz_state.viz.col_cat_offset * total_col_attrs;

  viz_state.viz.col_region =
    (viz_state.viz.col_cat_height + viz_state.viz.extra_space.col) *
      total_col_attrs +
    viz_state.viz.col_label;

  viz_state.viz.row_region =
    (viz_state.viz.row_cat_width + viz_state.viz.extra_space.row) *
      total_row_attrs +
    viz_state.viz.row_label;

  viz_state.viz.col_width = viz_state.viz.mat_width / viz_state.mat.num_cols;
  viz_state.viz.row_offset = viz_state.viz.mat_height / viz_state.mat.num_rows;
  viz_state.viz.col_offset = viz_state.viz.mat_width / viz_state.mat.num_cols;

  viz_state.viz.cat_shift_col = viz_state.viz.col_label;
  viz_state.zoom.ini_pan_x = viz_state.viz.mat_width / 2;
  viz_state.zoom.ini_pan_y =
    viz_state.viz.mat_height / 2 + viz_state.viz.row_offset;
};

const build_cat_data_for_axis = (viz_state, axis) => {
  const is_row = axis === 'row';
  const cat_offset = is_row
    ? viz_state.viz.row_cat_offset
    : viz_state.viz.col_cat_offset;
  const node_offset = is_row
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;

  const attr_defs = viz_state.attr.all_defs[axis] || [];
  const cat_data = [];

  attr_defs.forEach((def, attr_index) => {
    const values = def.values || [];
    const max_abs = def.maxabs || 0;
    const color_map = def.color_map || {};

    values.forEach((value, node_index) => {
      if (value === null || value === undefined || value === '') return;

      let color;
      if (def.type === 'numeric') {
        const max_val = Math.abs(max_abs) || 1;
        const val = Number(value);
        if (Number.isNaN(val)) return;

        const neg = [255, 165, 0];
        const pos = [169, 169, 169];
        const palette = val >= 0 ? pos : neg;
        const alpha = Math.min(1, Math.abs(val) / max_val);
        color = [...palette, Math.round(alpha * 255)];
      } else {
        const key = ensure_string(value);
        const chosen =
          color_map[key] || fallback_color(key, node_index + attr_index);
        color = colorToRgba(chosen, 255);
      }

      cat_data.push({
        position: is_row
          ? [
              cat_offset * (attr_index + 0.5) + 20,
              node_offset * (node_index + 0.5),
            ]
          : [
              node_offset * (node_index + 0.5),
              cat_offset * (attr_index + 1.5) - 30,
            ],
        color,
        name: def.type === 'numeric' ? value : ensure_string(value),
        level: attr_index,
        original_index: node_index,
      });
    });
  });

  return cat_data;
};

const update_combined_attr_defs = (viz_state) => {
  ['row', 'col'].forEach((axis) => {
    const combined_defs = [
      ...(viz_state.attr.static_defs?.[axis] || []),
      ...(viz_state.attr.manual_defs?.[axis] || []),
    ];

    viz_state.attr.all_defs[axis] = combined_defs;
    viz_state.attr.names[axis] = combined_defs.map(
      (definition) => definition.name
    );
    viz_state.attr.maxabs[axis] = combined_defs.map((definition) =>
      definition.type === 'numeric' ? (definition.maxabs ?? 0) : null
    );
    viz_state.attr.num[axis] = combined_defs.length;
  });
};

const build_static_definitions = (viz_state, network, axis) => {
  const nodes = axis === 'row' ? network.row_nodes : network.col_nodes;
  const attribute_names = viz_state.attr.names[axis] || [];
  const max_abs_values = viz_state.attr.maxabs[axis] || [];

  return attribute_names.map((attribute_name, index) => {
    const is_numeric =
      max_abs_values[index] !== null && max_abs_values[index] !== undefined;

    if (is_numeric) {
      const values = nodes.map((node) => node[`num-${index}`]);
      return {
        name: attribute_name,
        type: 'numeric',
        values,
        maxabs: max_abs_values[index],
      };
    }

    const raw_values = nodes.map((node) => ensure_string(node[`cat-${index}`]));
    const colors = {};

    raw_values.forEach((value, value_index) => {
      if (value === null) return;

      if (network.global_cat_colors && network.global_cat_colors[value]) {
        colors[value] = network.global_cat_colors[value];
      } else if (!colors[value]) {
        colors[value] = fallback_color(value, value_index);
      }
    });

    return {
      name: attribute_name,
      type: 'categorical',
      values: raw_values,
      color_map: colors,
    };
  });
};

export const initialize_attr_state = (viz_state, network) => {
  viz_state.attr.static_defs = { row: [], col: [] };
  viz_state.attr.manual_defs = { row: [], col: [] };
  viz_state.attr.all_defs = { row: [], col: [] };
  viz_state.attr.names = viz_state.attr.names || { row: [], col: [] };
  viz_state.attr.maxabs = viz_state.attr.maxabs || { row: [], col: [] };
  viz_state.attr.num = viz_state.attr.num || { row: 0, col: 0 };

  viz_state.attr.category_colors = {};
  viz_state.attr.did_initialize = false;

  viz_state.manual_cat = viz_state.manual_cat || {
    config: { row: null, col: null },
    flags: { row: false, col: false },
  };

  viz_state.attr.static_defs.row = build_static_definitions(
    viz_state,
    network,
    'row'
  );
  viz_state.attr.static_defs.col = build_static_definitions(
    viz_state,
    network,
    'col'
  );

  update_combined_attr_defs(viz_state);
};

export const refresh_attribute_layers = (deck_mat, layers_mat, viz_state) => {
  compute_geometry(viz_state);

  const row_data = build_cat_data_for_axis(viz_state, 'row');
  const col_data = build_cat_data_for_axis(viz_state, 'col');

  viz_state.cats.row_cat_data = row_data;
  viz_state.cats.col_cat_data = col_data;

  layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
    data: row_data,
    tile_width: (viz_state.viz.row_cat_width / 2) * 0.9,
    tile_height: (viz_state.viz.mat_height / viz_state.mat.num_rows) * 0.5,
  });

  layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
    data: col_data,
    tile_width: (viz_state.viz.mat_width / viz_state.mat.num_cols) * 0.5,
    tile_height: viz_state.viz.col_cat_height / 2,
  });

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    tile_height: (viz_state.viz.mat_height / viz_state.mat.num_rows) * 0.5,
    tile_width: (viz_state.viz.mat_width / viz_state.mat.num_cols) * 0.5,
    updateTriggers: {
      getPosition: [viz_state.order.current.row, viz_state.order.current.col],
    },
  });

  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    data: viz_state.labels.row_label_data,
    updateTriggers: { getPosition: viz_state.order.current.row },
  });

  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    data: viz_state.labels.col_label_data,
    updateTriggers: { getPosition: viz_state.order.current.col },
  });

  ini_views(viz_state);
  const view_state = ini_view_state(viz_state);

  const props = {
    views: viz_state.views.views_list,
    layers: get_mat_layers_list(layers_mat),
  };

  if (!viz_state.attr.did_initialize) {
    props.initialViewState = view_state;
    viz_state.attr.did_initialize = true;
  }

  deck_mat.setProps(props);
};

export const apply_manual_definitions_to_axis = (viz_state, axis) => {
  const normalized_axis = normalize_axis(axis);
  const flags = viz_state.manual_cat?.flags || {};
  const manual_store = viz_state.obs_store?.manual_cat?.[normalized_axis];

  const attribute_name = manual_store?.attribute || null;
  const configured_name =
    viz_state.manual_cat?.config?.[normalized_axis]?.attribute || null;
  const target_attribute = attribute_name || configured_name;
  const is_enabled = !!(flags[normalized_axis] && attribute_name);

  // If disabled or no store, clear manual defs for this axis
  if (!is_enabled || !manual_store || !target_attribute) {
    viz_state.attr.manual_defs[normalized_axis] = [];
    update_combined_attr_defs(viz_state);
    return true;
  }

  // Build values aligned to current node order
  const manual_frame = manual_store.toFrame(MANUAL_FILL_VALUE);
  const manual_colors = manual_store.toColorPayload(
    MANUAL_FILL_VALUE,
    MANUAL_FILL_COLOR
  );

  const index_labels = (manual_frame.index || []).map((label) => String(label));
  const index_lookup = new Map();
  index_labels.forEach((label, idx) => {
    index_lookup.set(label, idx);
  });

  const nodes =
    normalized_axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const node_names = nodes.map((node) => String(node.name));
  const series = manual_frame.data[target_attribute] || [];

  const values = node_names.map((name) => {
    const idx = index_lookup.get(name);
    if (idx === undefined) return null;
    const value = series[idx];
    return value === null || value === undefined ? null : value;
  });

  // Build color map
  const manual_color_map = manual_colors[target_attribute] || {};
  const stored_colors = viz_state.attr.category_colors || {};
  const unique_values = Array.from(
    new Set(values.filter((val) => val !== null && val !== ''))
  );

  const color_map = {};
  unique_values.forEach((val, idx) => {
    color_map[val] =
      manual_color_map[val] || stored_colors[val] || fallback_color(val, idx);
  });

  // Update global category_colors
  const category_colors = viz_state.attr.category_colors || {};
  Object.entries(color_map).forEach(([value, hex]) => {
    if (value && hex && category_colors[value] !== hex) {
      category_colors[value] = hex;
    }
  });
  viz_state.attr.category_colors = category_colors;

  // Store a single manual def for this axis
  viz_state.attr.manual_defs[normalized_axis] = [
    {
      name: target_attribute,
      type: 'categorical',
      values,
      color_map,
    },
  ];

  update_combined_attr_defs(viz_state);
  return true;
};
