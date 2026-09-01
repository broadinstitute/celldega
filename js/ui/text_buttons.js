import * as d3 from 'd3';

import { new_toggle_cell_layer_visibility } from '../deck-gl/layers/cell_layer';
import { toggle_visibility_single_image_layer } from '../deck-gl/layers/image_layers';
import { toggle_nbhd_cloud_shapes_layer_visibility } from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { toggle_nbhd_layer_visibility } from '../deck-gl/layers/nbhd_layer';
import { toggle_path_layer_visibility } from '../deck-gl/layers/path_layer';
import { toggle_trx_layer_visibility } from '../deck-gl/layers/trx_layer';
import {
  refresh_composition_dendro,
  toggle_dendro_layer_visibility,
} from '../deck-gl/matrix/dendro_layers';
import {
  col_label_color_triggers,
  get_layer_update_triggers,
  get_mat_layers_list,
  mat_reorder_triggers,
  row_label_color_triggers,
} from '../deck-gl/matrix/matrix_layers';
import { refresh_row_label_visibility } from '../matrix/composition_data';
import { crop_filter_signature } from '../matrix/crop_filter';
import { refresh_layer } from '../utils/refresh_layer';

import { toggle_slider } from './sliders';

let is_visible;

let img_layer_visible = true;

export const get_img_layer_visible = () => img_layer_visible;

const set_img_layer_visible = (visible) => {
  img_layer_visible = visible;
};

const toggle_visible_button = (event) => {
  const current = d3.select(event.currentTarget);

  if (current.style('color') === 'blue') {
    current.style('color', 'gray');
    is_visible = false;
  } else {
    current.style('color', 'blue');
    is_visible = true;
  }

  return is_visible;
};

/**
 * Style a control-panel text button by active state: text color alone
 * indicates state (blue = active, gray = inactive) — no border/background.
 *
 * @param {object} selection - d3 selection of the button element.
 * @param {boolean} isActive - Whether the button is in the active state.
 * @param {object} viz_state - Visualization state (for the color constants).
 */
export const apply_state_button_style = (selection, isActive, viz_state) =>
  selection
    .style(
      'color',
      isActive ? viz_state.buttons.text_active : viz_state.buttons.text_inactive
    )
    .style('cursor', 'pointer')
    .style('font-weight', 'bold')
    .style('user-select', 'none');

/**
 * Reset every reorder button for an axis back to the inactive text color,
 * e.g. when a different reorder mechanism (attribute double-click, custom
 * label reorder) takes over ordering for that axis.
 *
 * @param {object} viz_state - Visualization state.
 * @param {string} axis - "row" or "col".
 */
export const deselect_reorder_buttons = (viz_state, axis) => {
  d3.select(viz_state.el)
    .selectAll(`.button-${axis}`)
    .classed('active', false)
    .style('color', viz_state.buttons.text_inactive);
};

const reorder_button_callback = (
  event,
  axis,
  deck_mat,
  layers_mat,
  viz_state
) => {
  const current = d3.select(event.currentTarget);

  let button_name = current.text().toLowerCase();

  // quick fix for naming mismatch
  if (button_name === 'var') {
    button_name = 'rankvar';
  } else if (button_name === 'sum') {
    button_name = 'rank';
  }

  const is_active = current.classed('active');

  if (is_active === false) {
    current.classed('active', true);

    deselect_reorder_buttons(viz_state, axis);

    apply_state_button_style(current, true, viz_state).classed('active', true);

    viz_state.order.current[axis] = button_name;

    layers_mat.mat_layer = layers_mat.mat_layer.clone({
      updateTriggers: mat_reorder_triggers(viz_state),
    });

    if (axis === 'row') {
      layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        updateTriggers: {
          ...get_layer_update_triggers(layers_mat.row_label_layer),
          getPosition: [
            viz_state.order.current.row,
            crop_filter_signature(viz_state),
          ],
        },
      });

      // reorder cat_layer
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        updateTriggers: {
          ...get_layer_update_triggers(layers_mat.row_cat_layer),
          getPosition: [
            viz_state.order.current.row,
            crop_filter_signature(viz_state),
          ],
        },
      });
    } else {
      layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        updateTriggers: {
          ...get_layer_update_triggers(layers_mat.col_label_layer),
          getPosition: [
            viz_state.order.current.col,
            crop_filter_signature(viz_state),
          ],
        },
      });

      // reorder cat_layer
      layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
        updateTriggers: {
          ...get_layer_update_triggers(layers_mat.col_cat_layer),
          getPosition: [
            viz_state.order.current.col,
            crop_filter_signature(viz_state),
          ],
        },
      });
    }

    // A button reorder replaces any double-click custom order, so re-trigger
    // both axes' label colors: the blue reorder-driver label (valid only
    // while the sorted axis is still 'custom') reverts to black.
    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.row_label_layer),
        getColor: row_label_color_triggers(viz_state),
      },
    });
    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.col_label_layer),
        getColor: col_label_color_triggers(viz_state),
      },
    });

    // Composition mode: row labels are positioned by their actual segment
    // (which moves on either a row or a column reorder) and filtered by fit,
    // so refresh on any reorder. No-op outside composition mode. Same for the
    // row dendrogram, whose leaves come from the rightmost bar's segments.
    refresh_row_label_visibility(layers_mat, viz_state);
    refresh_composition_dendro(layers_mat, viz_state);

    toggle_dendro_layer_visibility(layers_mat, viz_state, axis);

    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }
};

export const make_reorder_button = (
  container,
  text,
  active,
  width = 40,
  axis,
  deck_mat,
  layers_mat,
  viz_state
) => {
  const button_class = `button-${axis}`;

  // Keep original uppercase text for display
  const display_text = text.toUpperCase();

  const selection = d3
    .select(container)
    .append('div')
    .classed(button_class, true)
    .classed('active', active)
    .text(display_text)
    .style('width', `${width}px`)
    .style('height', '16px')
    .style('display', 'inline-flex')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('text-align', 'center')
    .style('font-size', '9px')
    .style('margin-top', '4px')
    .style('margin-left', '3px')
    .style('padding', '2px 4px')
    .style(
      'font-family',
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
    )
    .on('click', (event) =>
      reorder_button_callback(event, axis, deck_mat, layers_mat, viz_state)
    );

  apply_state_button_style(selection, active, viz_state);
};

const BUTTON_FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

/**
 * A row of mutually-exclusive text-toggle options rendered as
 * "LABEL_A | LABEL_B" (e.g. "HEIGHT | OPACITY"), the active option in blue,
 * the rest gray. The "|" separators are static, non-interactive.
 *
 * @param {HTMLElement} container - Parent element to append into.
 * @param {Array<{label: string, value: *}>} options - Options, in display order.
 * @param {*} initialValue - Which option's `value` starts active.
 * @param {(value: *) => void} onSelect - Called with the newly active option's value.
 * @param {object} viz_state - Visualization state (for color constants).
 * @returns {{container: HTMLElement, setActive: (value: *) => void}}
 */
export const make_text_toggle_group = (
  container,
  options,
  initialValue,
  onSelect,
  viz_state
) => {
  const row = d3
    .select(container)
    .append('div')
    .style('display', 'inline-flex')
    .style('align-items', 'center')
    .style('margin-top', '4px')
    .style('margin-left', '3px')
    .style('font-family', BUTTON_FONT_FAMILY);

  const spans = [];

  const setActive = (activeValue) => {
    spans.forEach(({ value, selection }) =>
      apply_state_button_style(selection, value === activeValue, viz_state)
    );
  };

  options.forEach((opt, i) => {
    if (i > 0) {
      row
        .append('div')
        .text('|')
        .style('color', 'black')
        .style('font-size', '9px')
        .style('font-weight', 'bold')
        .style('margin', '0 3px');
    }
    const selection = row
      .append('div')
      .text(opt.label.toUpperCase())
      .style('display', 'inline-flex')
      .style('font-size', '9px')
      .on('click', () => {
        setActive(opt.value);
        onSelect(opt.value);
      });
    spans.push({ value: opt.value, selection });
  });

  setActive(initialValue);

  return { container: row.node(), setActive };
};

const ist_img_button_callback = async (
  event,
  _deck_ist,
  _layers_obj,
  viz_state
) => {
  toggle_visible_button(event);
  const show = is_visible;

  if (viz_state.obs_store.umap_state.get() && show) {
    viz_state.obs_store.landscape_view.set('spatial');
  } else {
    viz_state.obs_store.viz_image_layers.set(show);
    viz_state.obs_store.viz_background_layer.set(show);
  }

  set_img_layer_visible(show);
};

const trx_button_callback_ist = async (
  event,
  deck_ist,
  layers_obj,
  viz_state
) => {
  toggle_visible_button(event);
  toggle_slider(viz_state.sliders.trx, is_visible);
  toggle_trx_layer_visibility(layers_obj, is_visible);

  if (is_visible) {
    toggle_nbhd_layer_visibility(layers_obj, false);
    viz_state.obs_store.viz_nbhd_layer.set(false);
    viz_state.obs_store.viz_edit_layer.set(false);

    if (viz_state.nbhd.is_nbhd) {
      viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');
    }

    viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);
  } else {
    viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 0.2);
  }

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    trx_layer: false,
  });

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    trx_layer: true,
  });
};

const cell_button_callback = async (event, deck_ist, layers_obj, viz_state) => {
  toggle_visible_button(event);
  toggle_slider(viz_state.sliders.cell, is_visible);

  new_toggle_cell_layer_visibility(layers_obj, is_visible);
  toggle_path_layer_visibility(layers_obj, is_visible);

  if (is_visible) {
    toggle_nbhd_layer_visibility(layers_obj, false);
    viz_state.obs_store.viz_nbhd_layer.set(false);
    viz_state.obs_store.viz_edit_layer.set(false);

    if (viz_state.nbhd.is_nbhd) {
      viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');
    }

    viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 1.0);
  } else {
    viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 0.2);
  }

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    nbhd_layer: false,
  });

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: true,
    path_layer: true,
    nbhd_layer: true,
  });
};

const nbhd_button_callback = async (event, deck_ist, layers_obj, viz_state) => {
  toggle_visible_button(event);

  toggle_slider(viz_state.sliders.nbhd, is_visible);

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    // neighborhood-cloud has no exclusive "active layer" concept -- shapes
    // and cells coexist via the zoom crossfade, so this only needs to
    // show/hide the shapes layer itself, not juggle image/cell/path/trx
    // layer visibility the way the legacy 2D nbhd feature does below.
    toggle_nbhd_cloud_shapes_layer_visibility(layers_obj, is_visible);
    refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
    return;
  }

  toggle_nbhd_layer_visibility(layers_obj, is_visible);

  viz_state.obs_store.viz_nbhd_layer.set(is_visible);

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    // reset image layers
    image_layers: false,
    nbhd_layer: false,
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    image_layers: true,
    nbhd_layer: true,
    cell_layer: true,
    path_layer: true,
    trx_layer: true,
  });
};

const umap_button_callback = async (
  _event,
  _deck_ist,
  _layers_obj,
  viz_state
) => {
  viz_state.obs_store.landscape_view.set('umap');
};

const spatial_button_callback = async (
  _event,
  _deck_ist,
  _layers_obj,
  viz_state
) => {
  viz_state.obs_store.landscape_view.set('spatial');
};

const make_ist_img_layer_button_callback = (
  text,
  deck_ist,
  layers_obj,
  viz_state
) => {
  return async (event) => {
    const inUmap = viz_state.obs_store.umap_state.get();

    if (!img_layer_visible && !inUmap) {
      return;
    }

    toggle_visible_button(event);

    if (inUmap) {
      viz_state.obs_store.landscape_view.set('spatial');
      viz_state.obs_store.viz_background_layer.set(true);
      viz_state.obs_store.viz_image_layers.set(true);
    }

    toggle_visibility_single_image_layer(layers_obj, text, is_visible);

    const inst_slider = viz_state.img.image_layer_sliders.filter(
      (slider) => slider.name === text
    )[0];

    toggle_slider(inst_slider, is_visible);

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      image_layers: false,
    });

    viz_state.layers_obj = layers_obj;

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      image_layers: true,
    });
  };
};

export const make_button = (
  container,
  _technology,
  text,
  color = 'blue',
  width = 40,
  button_class = 'button',
  inst_deck,
  layers_obj,
  viz_state
) => {
  let callback;

  if (text === 'IMG') {
    callback = (event) =>
      ist_img_button_callback(event, inst_deck, layers_obj, viz_state);
  } else if (text === 'TRX') {
    callback = (event) =>
      trx_button_callback_ist(event, inst_deck, layers_obj, viz_state);
  } else if (text === 'CELL') {
    callback = (event) =>
      cell_button_callback(event, inst_deck, layers_obj, viz_state);
  } else if (text === 'NBHD') {
    callback = (event) =>
      nbhd_button_callback(event, inst_deck, layers_obj, viz_state);
  } else if (text === 'UMAP') {
    callback = (event) =>
      umap_button_callback(event, inst_deck, layers_obj, viz_state);
  } else if (text === 'SPATIAL') {
    callback = (event) =>
      spatial_button_callback(event, inst_deck, layers_obj, viz_state);
  } else {
    callback = make_ist_img_layer_button_callback(
      text,
      inst_deck,
      layers_obj,
      viz_state
    );
  }

  const inst_button = d3
    .select(container)
    .append('div')
    .attr('class', button_class)
    .text(text)
    .style('width', `${width}px`)
    .style('text-align', 'left')
    .style('cursor', 'pointer')
    .style('font-size', '12px')
    .style('font-weight', 'bold')
    .style('color', color)
    .style('margin-top', '5px')
    .style('margin-left', '5px')
    .style('user-select', 'none')
    .style(
      'font-family',
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif;'
    )
    .on('click', callback);

  const button_name = text.toLowerCase();
  viz_state.buttons.buttons[button_name] = inst_button;
};

export const make_edit_button = (
  deck_ist,
  layers_obj,
  viz_state,
  container,
  text,
  width,
  edit_button_callback
) => {
  const button_class = 'edit_button';

  const active = false;

  // make text all caps
  text = text.toUpperCase();

  const inst_button = d3
    .select(container)
    .append('div')
    .classed(button_class, true)
    .classed('active', active)
    .text(text)
    .style('width', `${width}px`)
    .style('height', '20px') // Adjust height for button padding
    .style('display', 'inline-flex')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('text-align', 'center')
    .style('cursor', 'pointer')
    .style('font-size', '12px')
    .style('font-weight', 'bold')
    .style('color', 'gray')
    // .style('border', '3px solid')  // Light gray border
    // .style('border-color', color)  // Light gray border
    // .style('border-radius', '12px')  // Rounded corners
    // .style('margin-top', '5px')
    .style('margin-left', '3px')
    // .style('padding', '4px 10px')  // Padding inside the button
    .style('user-select', 'none')
    .style(
      'font-family',
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
    )
    .on('click', (event) =>
      edit_button_callback(event, deck_ist, layers_obj, viz_state)
    )
    .node();

  const button_name = text.toLowerCase();
  viz_state.edit.buttons[button_name] = inst_button;
};
