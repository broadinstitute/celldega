import * as d3 from 'd3';

import {
  crop_fade_alpha_factor,
  crop_fade_signature,
  crop_filter_signature,
  filter_matrix_data,
  get_axis_center_position,
  get_axis_slot_size,
} from '../../matrix/crop_filter';
import { apply_mat_encoding } from '../../matrix/mat_data';

import { CustomMatrixLayer } from './custom_matrix_layer';
import {
  clear_dendro_hover,
  dendro_highlight_alpha_factor,
} from './dendro_layers';
import { get_mat_layers_list, get_matrix_body_layer_id } from './matrix_layers';

const mat_layer_get_fill_color = (d, viz_state) => {
  const alpha_factor =
    dendro_highlight_alpha_factor(viz_state, d.row, d.col) *
    crop_fade_alpha_factor(viz_state, d.row, d.col);
  if (alpha_factor === 1) return d.color;

  return [d.color[0], d.color[1], d.color[2], d.color[3] * alpha_factor];
};

const mat_layer_get_position = (d, viz_state) => {
  const pos_x = get_axis_center_position(viz_state, 'col', d.col);
  const pos_y = get_axis_center_position(viz_state, 'row', d.row);

  return [pos_x ?? d.position?.[0] ?? 0, pos_y ?? d.position?.[1] ?? 0];
};

export const ini_mat_layer = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  const fade_sig = crop_fade_signature(viz_state);
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
    // Animate size + opacity so switching viz_mode (heatmap/size/dotplot) is fun.
    getRadius: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
    getFillColor: {
      duration: 120,
      easing: d3.easeCubic,
    },
  };

  const mat_layer = new CustomMatrixLayer({
    id: get_matrix_body_layer_id(viz_state),
    data: filter_matrix_data(viz_state),
    getPosition: (d) => mat_layer_get_position(d, viz_state),
    getFillColor: (d) => mat_layer_get_fill_color(d, viz_state),
    // Per-cell size scale in [0, 1] consumed by the custom vertex shader.
    getRadius: (d) => d.size_scale,
    pickable: true,
    antialiasing: false,
    tile_height: get_axis_slot_size(viz_state, 'row') * 0.5,
    tile_width: get_axis_slot_size(viz_state, 'col') * 0.5,
    updateTriggers: {
      getPosition: crop_sig,
      getRadius: crop_sig,
      getFillColor: [crop_sig, fade_sig, viz_state.dendro?._highlight_rev || 0],
    },
    transitions,
  });

  return mat_layer;
};

const mat_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {
  const row_index = event.object.row;
  const col_index = event.object.col;
  const row_name = viz_state.labels.row_label_data[row_index].name;
  const col_name = viz_state.labels.col_label_data[col_index].name;

  // Get the actual matrix value
  const mat_value = viz_state.mat.net_mat[row_index][col_index];

  viz_state.click.type = 'mat_value';
  viz_state.click.value = {
    row: {
      name: row_name,
      index: row_index,
      // New structured entity info
      entity: viz_state.row_entity.entity,
      attr: viz_state.row_entity.attr,
      // Legacy field for backwards compatibility
      row_entity: viz_state.row_entity.entity,
    },
    col: {
      name: col_name,
      index: col_index,
      // New structured entity info
      entity: viz_state.col_entity.entity,
      attr: viz_state.col_entity.attr,
      // Legacy field for backwards compatibility
      col_entity: viz_state.col_entity.entity,
    },
    // The actual matrix cell value
    value: mat_value,
    // Full entity info for both axes
    row_entity_full: viz_state.row_entity,
    col_entity_full: viz_state.col_entity,
  };

  // Update the clustergram store with selected cell info
  if (viz_state.obs_store?.selected_cell) {
    viz_state.obs_store.selected_cell.set({
      row_name,
      col_name,
      row_index,
      col_index,
      value: mat_value,
    });
  }

  if (viz_state.model?.set) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  // Close the attribute editor on matrix click
  if (viz_state.attr?.editor?.close) {
    viz_state.attr.editor.close();
  }
};

export const set_mat_layer_onclick = (deck_mat, layers_mat, viz_state) => {
  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    // not using event or d
    onClick: (event) =>
      mat_layer_onclick(event, deck_mat, layers_mat, viz_state),
  });
};

/**
 * Proactively clear the dendrogram hover highlight whenever a cell/segment
 * is actively hovered — the matrix body and the dendrogram (which sits
 * beside it) can't both be legitimately hovered at once, so this covers the
 * "moved from the dendrogram back onto the body" transition even if the
 * dendrogram layer's own onHover(null) doesn't fire for some reason (e.g. a
 * picking edge case at a viewport boundary).
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const set_mat_layer_onhover = (deck_mat, layers_mat, viz_state) => {
  const on_hover = (info) => {
    if (!info?.object) return;
    clear_dendro_hover(deck_mat, layers_mat, viz_state);
  };

  layers_mat.mat_layer = layers_mat.mat_layer.clone({ onHover: on_hover });
};

/**
 * Toggle whether dotplot dot size encodes the secondary (fraction) matrix
 * (true, default) or is forced to a full tile (false), independent of the
 * color/opacity channel. No-op outside dotplot mode.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {boolean} value - New `dot_size_encoded` value.
 */
export const set_dot_size_encoded = (
  deck_mat,
  layers_mat,
  viz_state,
  value
) => {
  viz_state.mat.dot_size_encoded = value;

  if (viz_state.model?.set) {
    viz_state.model.set('dot_size_encoded', value);
    viz_state.model.save_changes();
  }

  if (viz_state.mat.viz_mode !== 'dotplot') return;

  apply_mat_encoding(viz_state);
  const crop_sig = crop_filter_signature(viz_state);
  const fade_sig = crop_fade_signature(viz_state);
  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    data: filter_matrix_data(viz_state),
    updateTriggers: {
      getPosition: crop_sig,
      getRadius: [value, crop_sig],
      getFillColor: [crop_sig, fade_sig, viz_state.dendro?._highlight_rev || 0],
    },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};
