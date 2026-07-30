import * as d3 from 'd3';
import { TextLayer } from 'deck.gl';

import {
  sync_selected_genes,
  sync_selected_rows,
  sync_selected_cols,
} from '../../global_variables/selected_genes';
import {
  composition_row_label_position,
  refresh_row_label_visibility,
} from '../../matrix/composition_data';
import { deselect_reorder_buttons } from '../../ui/text_buttons';

import {
  apply_composition_hover_col,
  apply_composition_hover_row,
  clear_composition_hover,
  HOVER_HIGHLIGHT_DELAY_MS,
} from './composition_layer';
import {
  refresh_composition_dendro,
  toggle_dendro_layer_visibility,
} from './dendro_layers';
import { get_mat_layers_list, mat_reorder_triggers } from './matrix_layers';

const row_label_get_position = (d, index, viz_state) => {
  const inst_index = index.index;

  // Composition mode: position at the row's actual stacked-bar segment
  // (next to the leftmost bar) so labels track reordering/normalization
  // exactly, rather than a uniform heatmap-style slot.
  if (viz_state.mat.viz_mode === 'composition') {
    return composition_row_label_position(viz_state, inst_index);
  }

  const inst_order = viz_state.order.current.row;
  const row_offset = 50; // 25

  const inst_row_index =
    viz_state.mat.num_rows - viz_state.mat.orders.row[inst_order][inst_index];

  const pos_x = row_offset;
  const pos_y = viz_state.viz.row_offset * (inst_row_index + 1.5);

  const position = [pos_x, pos_y];

  return position;
};

const col_label_get_position = (d, index, viz_state) => {
  const inst_index = index.index;
  const inst_order = viz_state.order.current.col;
  const col_offset = 50;

  const inst_col_index =
    viz_state.mat.num_cols - viz_state.mat.orders.col[inst_order][inst_index];

  const pos_x = viz_state.viz.col_offset * (inst_col_index + 0.5);
  const pos_y = col_offset; // * zoom_factor

  const position = [pos_x, pos_y];

  return position;
};

export const ini_row_label_layer = (viz_state) => {
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const row_label_layer = new TextLayer({
    id: 'row-label-layer',
    data: viz_state.labels.row_label_data,
    getPosition: (d, index) => row_label_get_position(d, index, viz_state),
    getText: (d) => d.display_name || d.name,
    getSize: viz_state.viz.font_size.rows,
    // Per-instance so composition mode can hide labels that don't fit their
    // segment (fully transparent, rather than removed from `data`, so
    // reorder/index-keyed picking stays stable).
    getColor: (d) => {
      if (viz_state.mat.viz_mode !== 'composition') return [0, 0, 0, 255];
      const visible = viz_state.labels.row_visibility;
      return !visible || visible[d.index] !== false
        ? [0, 0, 0, 255]
        : [0, 0, 0, 0];
    },
    getAngle: 0,
    getTextAnchor: 'end',
    getAlignmentBaseline: 'center',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 2,
    updateTriggers: {
      getColor: viz_state.labels._row_vis_rev || 0,
    },
    pickable: true,
    transitions,
  });

  return row_label_layer;
};

export const ini_col_label_layer = (viz_state) => {
  // Define zoom-dependent offset
  function getPixelOffset(zoom_x, num_cols) {
    const zoom_factor = Math.pow(2, zoom_x);
    const offset_y = 75 / num_cols;
    const scaled_offset_y = offset_y * zoom_factor;

    return [0, scaled_offset_y];
  }

  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const col_label_layer = new TextLayer({
    id: 'col-label-layer',
    data: viz_state.labels.col_label_data,
    getPosition: (d, index) => col_label_get_position(d, index, viz_state),
    getText: (d) => d.display_name || d.name,
    getSize: viz_state.viz.font_size.cols,
    getColor: [0, 0, 0],
    getAngle: 45, // Optional: Text angle in degrees
    getTextAnchor: 'start', // middle
    getAlignmentBaseline: 'bottom',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 2,
    // updateTriggers: {
    // //   getSize: viz_state.viz.ini_font_size,
    //   getPosition: viz_state.viz.font_size,
    //   getPixelOffset: viz_state.zoom.zoom_data.matrix.zoom_x,
    // },
    pickable: true,
    transitions,
    getPixelOffset: () =>
      getPixelOffset(
        viz_state.zoom.zoom_data.matrix.zoom_x,
        viz_state.mat.num_cols
      ),
  });

  return col_label_layer;
};

const DOUBLE_CLICK_DELAY = 250;

const custom_label_reorder = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  name,
  index
) => {
  let tmp_arr = [];
  const other_axis = axis === 'col' ? 'row' : 'col';

  // deactivate reordering buttons when setting a custom order
  deselect_reorder_buttons(viz_state, other_axis);

  if (axis === 'col') {
    tmp_arr = viz_state.mat.net_mat.map((inst_row) => inst_row[index]);
  } else {
    tmp_arr = viz_state.mat.net_mat[index];
  }

  // tmp_sort is an array of the indexes of the other axis that are ranked by the values of the selected index
  const tmp_sort = Array.from(tmp_arr.keys()).sort(
    (a, b) => tmp_arr[b] - tmp_arr[a]
  );

  const length_other_axis = tmp_sort.length;
  const ranked_sort = Array(length_other_axis);

  // convert tmp_sort into an array of the ranks of each index
  // Fill the ranks array with the rank of each index
  tmp_sort.forEach((columnIndex, rank) => {
    ranked_sort[columnIndex] = length_other_axis - rank; // Add 1 to make it 1-indexed
  });

  viz_state.mat.orders[other_axis].custom = ranked_sort;

  viz_state.order.current[other_axis] = 'custom';

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: mat_reorder_triggers(viz_state, [name]),
  });

  if (other_axis === 'col') {
    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
      updateTriggers: {
        getPosition: [viz_state.order.current.col, name],
      },
    });

    // reorder cat_layer
    layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
      updateTriggers: {
        getPosition: viz_state.order.current.col,
      },
    });

    toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');
  } else if (other_axis === 'row') {
    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
      updateTriggers: {
        getPosition: [viz_state.order.current.row, name],
      },
    });

    // reorder cat_layer
    layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
      updateTriggers: {
        getPosition: viz_state.order.current.row,
      },
    });

    toggle_dendro_layer_visibility(layers_mat, viz_state, 'row');
  }

  // Reordering (in particular a column reorder, which can change which
  // column is leftmost/rightmost) can change which row labels fit their
  // segment, and where the row dendrogram's leaves sit.
  refresh_row_label_visibility(layers_mat, viz_state);
  refresh_composition_dendro(layers_mat, viz_state);

  deck_mat.setProps({
    layers: get_mat_layers_list(layers_mat),
  });
};

const row_label_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {
  const visibility = viz_state.labels.row_visibility;
  if (visibility && visibility[event.object.index] === false) return;

  viz_state.labels.clicks.row += 1;

  if (viz_state.labels.clicks.row === 1) {
    viz_state.click.type = 'row_label';
    const { name } = event.object;
    // Include full entity info (entity type + attribute)
    viz_state.click.value = {
      name,
      // New structured entity info
      entity: viz_state.row_entity.entity,
      attr: viz_state.row_entity.attr,
      // Legacy field for backwards compatibility
      row_entity: viz_state.row_entity.entity,
    };

    setTimeout(() => {
      viz_state.labels.clicks.row = 0;
    }, DOUBLE_CLICK_DELAY);

    if (viz_state.model?.set) {
      viz_state.model.set('click_info', null);
      viz_state.model.set('click_info', viz_state.click);
      viz_state.model.save_changes();
    }

    // Sync selected row to Python model
    sync_selected_rows(viz_state, [name]);
    // Also sync to selected_genes for backwards compatibility
    sync_selected_genes(viz_state, [name]);

    if (typeof viz_state.custom_callbacks.row === 'function') {
      viz_state.custom_callbacks.row(name);
    }
  } else if (viz_state.labels.clicks.row === 2) {
    viz_state.labels.clicks.row = 0;

    custom_label_reorder(
      deck_mat,
      layers_mat,
      viz_state,
      'row',
      event.object.name,
      event.object.index
    );
  }
};

const col_label_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {
  viz_state.labels.clicks.col += 1;

  if (viz_state.labels.clicks.col === 1) {
    viz_state.click.type = 'col_label';
    const { name } = event.object;
    // Include full entity info (entity type + attribute)
    viz_state.click.value = {
      name,
      // New structured entity info
      entity: viz_state.col_entity.entity,
      attr: viz_state.col_entity.attr,
      // Legacy field for backwards compatibility
      col_entity: viz_state.col_entity.entity,
    };

    setTimeout(() => {
      viz_state.labels.clicks.col = 0;
    }, DOUBLE_CLICK_DELAY);

    if (viz_state.model?.set) {
      viz_state.model.set('click_info', null);
      viz_state.model.set('click_info', viz_state.click);
      viz_state.model.save_changes();
    }

    // Sync selected column to Python model
    sync_selected_cols(viz_state, [name]);

    const col_index = event.object.index;
    const values = viz_state.mat.net_mat.map((row) => row[col_index]);
    const sorted = Array.from(values.keys()).sort(
      (a, b) => values[b] - values[a]
    );
    const top_n = viz_state.top_n_genes || 15;
    const gene_names = sorted
      .slice(0, top_n)
      .map((i) => viz_state.row_nodes[i].name);
    sync_selected_genes(viz_state, gene_names);

    if (typeof viz_state.custom_callbacks.col === 'function') {
      viz_state.custom_callbacks.col(name);
    }
  } else if (viz_state.labels.clicks.col === 2) {
    viz_state.labels.clicks.col = 0;

    custom_label_reorder(
      deck_mat,
      layers_mat,
      viz_state,
      'col',
      event.object.name,
      event.object.index
    );
  }
};

export const set_row_label_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    onClick: (event) =>
      row_label_layer_onclick(event, deck_mat, layers_mat, viz_state),
  });
};

export const set_col_label_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    onClick: (event) =>
      col_label_layer_onclick(event, deck_mat, layers_mat, viz_state),
  });
};

/**
 * Composition-only: hovering a row label highlights that population across
 * every bar, after the same short dwell delay as hovering a bar segment
 * directly (`set_composition_layer_onhover`) — the two are equivalent ways
 * to reach the same cross-bar highlight, so they share its delay/apply/clear
 * functions for a consistent feel. No-op outside composition mode (plain
 * Clustergram row labels aren't part of this interaction).
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const set_row_label_layer_onhover = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  const on_hover = (info) => {
    if (viz_state.mat.viz_mode !== 'composition') return;

    const row = info?.object ? info.object.index : null;

    if (row === null || row === viz_state.mat.comp_hover_row) {
      if (row === null)
        clear_composition_hover(deck_mat, layers_mat, viz_state);
      return;
    }

    clearTimeout(viz_state.mat._comp_hover_timer);
    viz_state.mat._comp_hover_timer = setTimeout(
      () => apply_composition_hover_row(deck_mat, layers_mat, viz_state, row),
      HOVER_HIGHLIGHT_DELAY_MS
    );
  };

  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    onHover: on_hover,
  });
};

/**
 * Composition-only: hovering a column (dataset) label highlights that bar
 * (dims every other bar) after the same short dwell delay used everywhere
 * else in composition's hover-highlight family. No-op outside composition
 * mode.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const set_col_label_layer_onhover = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  const on_hover = (info) => {
    if (viz_state.mat.viz_mode !== 'composition') return;

    const col = info?.object ? info.object.index : null;

    if (col === null || col === viz_state.mat.comp_hover_col) {
      if (col === null)
        clear_composition_hover(deck_mat, layers_mat, viz_state);
      return;
    }

    clearTimeout(viz_state.mat._comp_hover_col_timer);
    viz_state.mat._comp_hover_col_timer = setTimeout(
      () => apply_composition_hover_col(deck_mat, layers_mat, viz_state, col),
      HOVER_HIGHLIGHT_DELAY_MS
    );
  };

  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    onHover: on_hover,
  });
};
