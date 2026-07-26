import { create_clustergram_store } from '../obs_store/clustergram_store';
import { ManualCategoryStore } from '../obs_store/manual_category_store';

import { initialize_attr_state } from './attr_state';
import { resolve_viz_mode } from './mat_data';

/**
 * Parse entity specification from string or object.
 * Handles both legacy string format and new {entity, attr} format.
 *
 * @param {string|object} value - Entity specification
 * @returns {{entity: string, attr: string}} Normalized entity object
 */
const parseEntitySpec = (value) => {
  if (!value) {
    return { entity: 'gene', attr: 'name' };
  }

  // If it's a string, try to parse as JSON first
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      if (parsed && typeof parsed === 'object') {
        return {
          entity: parsed.entity || 'custom',
          attr: parsed.attr || 'name',
        };
      }
    } catch {
      // Not JSON, handle as legacy string
      const legacyMapping = {
        gene: { entity: 'gene', attr: 'name' },
        cell_cluster: { entity: 'cell', attr: 'leiden' },
        cluster: { entity: 'cell', attr: 'leiden' },
        nbhd: { entity: 'nbhd', attr: 'name' },
        cell: { entity: 'cell', attr: 'name' },
        hextile: { entity: 'hextile', attr: 'name' },
      };
      return legacyMapping[value] || { entity: value, attr: 'name' };
    }
  }

  // Already an object
  if (typeof value === 'object') {
    return {
      entity: value.entity || 'custom',
      attr: value.attr || 'name',
    };
  }

  return { entity: 'custom', attr: 'name' };
};

export const set_mat_constants = (
  model,
  network,
  root,
  width,
  height,
  row_entity_raw,
  col_entity_raw,
  row_label_callback,
  col_label_callback,
  col_dendro_callback
) => {
  const viz_state = {};

  /////////////////////////////
  // Constants
  //////////////////////////////

  viz_state.root = root;

  viz_state.model = model;
  viz_state.obs_store = create_clustergram_store();

  // Colors for value (numeric) attributes
  // Default: gray for positive, orange for negative
  const default_value_colors = { positive: '#a9a9a9', negative: '#ffa500' };
  viz_state.value_colors =
    (model && typeof model.get === 'function' && model.get('value_colors')) ||
    default_value_colors;

  viz_state.custom_callbacks = {};
  viz_state.custom_callbacks.row = row_label_callback;
  viz_state.custom_callbacks.col = col_label_callback;
  viz_state.custom_callbacks.col_dendro = col_dendro_callback;

  viz_state.viz = {};
  viz_state.viz.height_margin = 100;

  viz_state.attr = {};
  viz_state.attr.names = {
    row: network.row_attr || [],
    col: network.col_attr || [],
  };
  viz_state.attr.maxabs = {
    row: network.row_attr_maxabs || [],
    col: network.col_attr_maxabs || [],
  };
  viz_state.attr.num = {
    row: viz_state.attr.names.row.length,
    col: viz_state.attr.names.col.length,
  };

  initialize_attr_state(viz_state, network);

  viz_state.root.style.height = `${height + viz_state.viz.height_margin}px`;

  // height of attribute bars
  viz_state.viz.row_cat_offset = 9;
  viz_state.viz.col_cat_offset = 9;

  viz_state.viz.total_width = width;
  viz_state.viz.total_height = height;

  viz_state.viz.mat_width =
    width - viz_state.viz.row_cat_offset * viz_state.attr.num.row;
  viz_state.viz.mat_height =
    height - viz_state.viz.col_cat_offset * viz_state.attr.num.col;

  viz_state.mat = {};
  viz_state.mat.num_rows = network.mat.length;
  viz_state.mat.num_cols = network.mat[0].length;

  viz_state.row_nodes = network.row_nodes;
  viz_state.col_nodes = network.col_nodes;

  viz_state.obs_store.manual_cat = {
    row: new ManualCategoryStore('row', () =>
      (viz_state.row_nodes || []).map((node) => String(node.name))
    ),
    col: new ManualCategoryStore('col', () =>
      (viz_state.col_nodes || []).map((node) => String(node.name))
    ),
  };

  viz_state.mat.net_mat = network.mat;

  viz_state.linkage = network.linkage;

  viz_state.viz.base_font_size = 125;

  viz_state.viz.col_label = 75; // 40
  viz_state.viz.row_label = 75; // 35

  viz_state.viz.extra_space = {};
  viz_state.viz.extra_space.row = 5; // 10;
  viz_state.viz.extra_space.col = 5; // 10;

  viz_state.zoom = {};
  viz_state.zoom.ini_zoom_x = 0;
  viz_state.zoom.ini_zoom_y = 0;

  // to do: adjust height
  viz_state.viz.row_cat_width = 8;
  viz_state.viz.col_cat_height = 8;

  // move rows labels left
  viz_state.viz.label_row_x = 15; // 15

  // move col labels up
  viz_state.viz.label_col_y = 25;

  viz_state.viz.cat_shift_row = 30;

  viz_state.viz.label_buffer = 1;

  viz_state.animate = {};
  viz_state.animate.duration = 2500;

  viz_state.viz.dendrogram_width = 15;

  // Parse entity specifications (supports both legacy string and new {entity, attr} format)
  const row_entity = parseEntitySpec(row_entity_raw);
  const col_entity = parseEntitySpec(col_entity_raw);

  viz_state.row_entity = row_entity;
  viz_state.col_entity = col_entity;

  //////////////////////////////
  // Variables
  //////////////////////////////
  // viz_state.viz.ini_font_size = viz_state.viz.base_font_size / viz_state.mat.num_rows
  viz_state.viz.font_size = {};
  viz_state.viz.font_size.rows =
    viz_state.viz.base_font_size / viz_state.mat.num_rows;
  viz_state.viz.font_size.cols =
    viz_state.viz.base_font_size / viz_state.mat.num_cols;

  viz_state.viz.col_region =
    (viz_state.viz.col_cat_height + viz_state.viz.extra_space.col) *
      viz_state.attr.num.col +
    viz_state.viz.col_label;

  viz_state.viz.row_region =
    (viz_state.viz.row_cat_width + viz_state.viz.extra_space.row) *
      viz_state.attr.num.row +
    viz_state.viz.row_label;

  viz_state.viz.col_width = viz_state.viz.mat_width / viz_state.mat.num_cols;
  viz_state.viz.row_offset = viz_state.viz.mat_height / viz_state.mat.num_rows;
  viz_state.viz.col_offset = viz_state.viz.mat_width / viz_state.mat.num_cols;

  // column category positioning
  viz_state.viz.cat_shift_col = viz_state.viz.col_label; // + viz_state.viz.extra_space.col
  viz_state.zoom.ini_pan_x = viz_state.viz.mat_width / 2;

  // not sure why I need to add row_offset?
  viz_state.zoom.ini_pan_y =
    viz_state.viz.mat_height / 2 + viz_state.viz.row_offset;

  // make mat_data from network_data
  //////////////////////////////////////

  // Assuming network.mat is an array of arrays
  viz_state.mat.mat_data = [];
  viz_state.mat.num_rows = network.mat.length;
  viz_state.mat.num_cols = network.mat[0].length;

  const abs_vals = network.mat.flat().map((x) => Math.abs(x));
  abs_vals.sort((a, b) => a - b);
  const perc_idx = Math.floor(0.99 * (abs_vals.length - 1));
  viz_state.mat.max_abs_value = abs_vals[perc_idx] || 1;

  // Secondary matrix (dot-plot size channel) and its normalization scale.
  const has_size_mat = Array.isArray(network.size_mat);
  viz_state.mat.max_size_value = has_size_mat
    ? network.size_mat.flat().reduce((m, x) => Math.max(m, Math.abs(x)), 0) || 1
    : 1;

  // Requested encoding mode (heatmap | size | dotplot); dotplot needs a size mat.
  const requested_mode =
    (model && typeof model.get === 'function' && model.get('viz_mode')) ||
    'heatmap';
  viz_state.mat.viz_mode = resolve_viz_mode(requested_mode, has_size_mat);

  // Composition (stacked-bar) body configuration. `composition_normalized`
  // defaults to true (each column normalized to 100%); set false for raw counts.
  viz_state.mat.composition_normalized =
    model && typeof model.get === 'function'
      ? model.get('composition_normalized') !== false
      : true;
  viz_state.global_cat_colors = network.global_cat_colors || {};

  viz_state.order = {};

  viz_state.order.current = {};
  viz_state.order.current.row = 'clust';
  viz_state.order.current.col = 'clust';

  viz_state.order.new = 'ini';

  viz_state.buttons = {};
  viz_state.buttons.blue = '#8797ff';
  viz_state.buttons.gray = '#EEEEEE';

  viz_state.click = {};
  viz_state.click.type = null;
  viz_state.click.value = null;

  viz_state.top_n_genes =
    (model && typeof model.get === 'function' && model.get('top_n_genes')) ||
    50;

  return viz_state;
};
