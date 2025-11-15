import * as d3 from 'd3-color';

import { color_to_rgba } from './cat_data';
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers';
import { ini_views, ini_view_state } from '../deck-gl/matrix/views';

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

const clone = (value) => JSON.parse(JSON.stringify(value));

const ensure_string = (value) =>
  value === null || value === undefined ? null : String(value);

const fallback_color = (value, index) => {
  const palette_color = FALLBACK_COLORS[index % FALLBACK_COLORS.length];
  if (typeof value === 'string') {
    const col = d3.color(value);
    if (col) {
      return value;
    }
  }
  return palette_color;
};

const compute_geometry = (viz_state) => {
  const total_row_attrs = viz_state.attr.num.row;
  const total_col_attrs = viz_state.attr.num.col;

  viz_state.viz.mat_width =
    viz_state.viz.total_width -
    viz_state.viz.row_cat_offset * total_row_attrs;
  viz_state.viz.mat_height =
    viz_state.viz.total_height -
    viz_state.viz.col_cat_offset * total_col_attrs;

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
  viz_state.zoom.ini_pan_y = viz_state.viz.mat_height / 2 + viz_state.viz.row_offset;
};

const build_cat_data_for_axis = (viz_state, axis) => {
  const is_row = axis === 'row';
  const nodes = is_row ? viz_state.row_nodes : viz_state.col_nodes;
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
      if (value === null || value === undefined || value === '') {
        return;
      }

      let color;
      if (def.type === 'numeric') {
        const max_val = Math.abs(max_abs) || 1;
        const val = Number(value);
        if (Number.isNaN(val)) {
          return;
        }
        const neg = [255, 165, 0];
        const pos = [169, 169, 169];
        const palette = val >= 0 ? pos : neg;
        const alpha = Math.min(1, Math.abs(val) / max_val);
        color = [...palette, Math.round(alpha * 255)];
      } else {
        const key = ensure_string(value);
        const chosen =
          color_map[key] || fallback_color(key, node_index + attr_index);
        color = color_to_rgba(chosen, 255);
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
      ...(viz_state.attr.editable_defs?.[axis] || []),
    ];

    viz_state.attr.all_defs[axis] = combined_defs;
    viz_state.attr.names[axis] = combined_defs.map((definition) => definition.name);
    viz_state.attr.maxabs[axis] = combined_defs.map((definition) =>
      definition.type === 'numeric' ? definition.maxabs ?? 0 : null
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
      if (value === null) {
        return;
      }
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
  viz_state.attr.editable_defs = { row: [], col: [] };
  viz_state.attr.all_defs = { row: [], col: [] };
  viz_state.attr.frames = { row: null, col: null };
  viz_state.attr.color_payload = { row: {}, col: {} };
  viz_state.attr.did_initialize = false;
  viz_state.manual_cat = {
    definitions: { row: {}, col: {} },
    config: { row: null, col: null },
    self_update: false,
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

export const apply_attribute_frame = (
  axis,
  frame_payload,
  color_payload,
  viz_state
) => {
  const normalized_axis = axis === 'col' ? 'col' : 'row';
  viz_state.attr.frames[normalized_axis] = frame_payload
    ? clone(frame_payload)
    : null;
  viz_state.attr.color_payload[normalized_axis] = color_payload
    ? clone(color_payload)
    : {};

  if (!frame_payload || !Array.isArray(frame_payload.columns)) {
    viz_state.attr.editable_defs[normalized_axis] = [];
    update_combined_attr_defs(viz_state);
    return;
  }

  const index_labels = (frame_payload.index || []).map((label) => String(label));
  const data = frame_payload.data || {};
  const columns = frame_payload.columns || [];

  const nodes =
    normalized_axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const node_names = nodes.map((node) => String(node.name));
  const index_lookup = new Map();
  index_labels.forEach((label, idx) => {
    index_lookup.set(label, idx);
  });

  const defs = columns.map((column) => {
    const series = data[column] || [];
    const ordered = node_names.map((name) => {
      const idx = index_lookup.get(String(name));
      if (idx === undefined) {
        return null;
      }
      const value = series[idx];
      if (value === null || value === undefined) {
        return null;
      }
      return value;
    });

    const valid_values = ordered.filter(
      (v) => v !== null && v !== undefined && v !== ''
    );
    const numeric_values = valid_values.filter(
      (v) => typeof v === 'number' && !Number.isNaN(v)
    );
    const is_numeric =
      numeric_values.length > 0 && numeric_values.length === valid_values.length;

    if (is_numeric) {
      const max_val =
        numeric_values.reduce(
          (acc, val) => Math.max(acc, Math.abs(Number(val))),
          0
        ) || 1;
      return {
        name: column,
        type: 'numeric',
        values: ordered.map((val) =>
          val === null || val === undefined ? null : Number(val)
        ),
        maxabs: max_val,
      };
    }

    const string_values = ordered.map((val) => ensure_string(val));
    const unique_values = Array.from(
      new Set(string_values.filter((val) => val !== null && val !== ''))
    );
    const color_map = {};
    const provided_colors = color_payload?.[column] || {};

    unique_values.forEach((val, idx) => {
      color_map[val] = provided_colors[val] || fallback_color(val, idx);
    });

    return {
      name: column,
      type: 'categorical',
      values: string_values,
      color_map,
    };
  });

  viz_state.attr.editable_defs[normalized_axis] = defs;
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
    updateTriggers: { getPosition: viz_state.order.current.row },
  });

  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    updateTriggers: { getPosition: viz_state.order.current.col },
  });

  ini_views(viz_state);
  const viewState = ini_view_state(viz_state);
  const props = {
    views: viz_state.views.views_list,
    layers: get_mat_layers_list(layers_mat),
  };

  if (!viz_state.attr.did_initialize) {
    props.initialViewState = viewState;
    viz_state.attr.did_initialize = true;
  }

  deck_mat.setProps(props);
};

export const ensure_frame_payload = (axis, viz_state) => {
  const normalizedAxis = axis === 'col' ? 'col' : 'row';
  const existing = viz_state.attr.frames?.[normalizedAxis];
  if (existing) {
    return clone(existing);
  }

  const nodes =
    normalizedAxis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  return {
    columns: [],
    index: nodes.map((node) => String(node.name)),
    index_name: normalizedAxis === 'row' ? 'row_id' : 'col_id',
    data: {},
  };
};

export const update_color_payload = (axis, viz_state) =>
  clone(viz_state.attr.color_payload?.[axis === 'col' ? 'col' : 'row'] || {});

const normalize_axis = (axis) => (axis === 'col' ? 'col' : 'row');

const ensure_manual_store = (viz_state, axis) => {
  if (!viz_state.manual_cat) {
    viz_state.manual_cat = {
      definitions: { row: {}, col: {} },
      config: { row: null, col: null },
      self_update: false,
    };
  } else {
    viz_state.manual_cat.definitions = viz_state.manual_cat.definitions || {
      row: {},
      col: {},
    };
    viz_state.manual_cat.config = viz_state.manual_cat.config || {
      row: null,
      col: null,
    };
  }

  const normalized = normalize_axis(axis);
  viz_state.manual_cat.definitions[normalized] =
    viz_state.manual_cat.definitions[normalized] || {};

  return viz_state.manual_cat.definitions[normalized];
};

export const update_manual_category_for_selection = (
  viz_state,
  axis,
  attribute_name,
  selection,
  category_value,
  color_hex
) => {
  const normalized_axis = normalize_axis(axis);
  const frame = ensure_frame_payload(normalized_axis, viz_state);
  const colors = update_color_payload(normalized_axis, viz_state);

  if (!Array.isArray(frame.columns)) {
    frame.columns = [];
  }
  if (!frame.data) {
    frame.data = {};
  }

  if (!frame.columns.includes(attribute_name)) {
    frame.columns.push(attribute_name);
    frame.data[attribute_name] = Array(frame.index.length).fill(null);
  } else if (!frame.data[attribute_name]) {
    frame.data[attribute_name] = Array(frame.index.length).fill(null);
  }

  const index_lookup = new Map(
    (frame.index || []).map((name, idx) => [String(name), idx])
  );

  const normalized_value =
    category_value === null || category_value === undefined || category_value === ''
      ? null
      : String(category_value);

  selection.forEach((name) => {
    const idx = index_lookup.get(String(name));
    if (idx === undefined) {
      return;
    }
    frame.data[attribute_name][idx] = normalized_value;
  });

  if (normalized_value) {
    const attr_colors = colors[attribute_name] || {};
    attr_colors[normalized_value] = color_hex;
    colors[attribute_name] = attr_colors;
  }

  apply_attribute_frame(normalized_axis, frame, colors, viz_state);

  const store = ensure_manual_store(viz_state, normalized_axis);
  const manual_entry = store[attribute_name] || { values: {}, colors: {} };
  manual_entry.values = manual_entry.values || {};
  manual_entry.colors = manual_entry.colors || {};

  selection.forEach((name) => {
    const key = String(name);
    if (normalized_value) {
      manual_entry.values[key] = normalized_value;
    } else {
      delete manual_entry.values[key];
    }
  });

  if (normalized_value && color_hex) {
    manual_entry.colors[normalized_value] = color_hex;
  }

  if (Object.keys(manual_entry.values).length === 0) {
    delete store[attribute_name];
  } else {
    store[attribute_name] = manual_entry;
  }

  return { frame, colors };
};

export const export_manual_category_payload = (viz_state) => {
  if (!viz_state.manual_cat || !viz_state.manual_cat.definitions) {
    return { row: {}, col: {} };
  }

  const build_axis_export = (axis) => {
    const definitions = viz_state.manual_cat.definitions[axis] || {};
    const payload = {};

    Object.entries(definitions).forEach(([attribute_name, entry]) => {
      const values = entry?.values || {};
      const color_map = entry?.colors || {};
      if (Object.keys(values).length === 0) {
        return;
      }
      payload[attribute_name] = {
        values: { ...values },
        colors: { ...color_map },
      };
    });

    return payload;
  };

  return {
    row: build_axis_export('row'),
    col: build_axis_export('col'),
  };
};

export const sync_manual_category_from_payload = (payload, viz_state) => {
  if (!viz_state.manual_cat) {
    ensure_manual_store(viz_state, 'row');
    ensure_manual_store(viz_state, 'col');
  }

  if (viz_state.manual_cat.self_update) {
    viz_state.manual_cat.self_update = false;
    return;
  }

  let parsed = payload;
  if (typeof payload === 'string') {
    try {
      parsed = payload ? JSON.parse(payload) : {};
    } catch {
      parsed = {};
    }
  }

  if (!parsed || typeof parsed !== 'object') {
    return;
  }

  const definitions = viz_state.manual_cat.definitions;
  ['row', 'col'].forEach((axis) => {
    const axis_payload = parsed[axis] || {};
    const axis_store = {};

    Object.entries(axis_payload).forEach(([attribute_name, entry]) => {
      const values = entry?.values || entry || {};
      const colors = entry?.colors || {};
      axis_store[attribute_name] = {
        values: { ...values },
        colors: { ...colors },
      };
    });

    definitions[axis] = axis_store;
  });
};
