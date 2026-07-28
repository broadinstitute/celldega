import { TextLayer } from 'deck.gl';

import { toggle_dendro_layer_visibility } from '../deck-gl/matrix/dendro_layers';
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers';
import { refresh_row_label_visibility } from '../matrix/composition_data';

import { deselect_reorder_buttons } from './text_buttons';

/**
 * Generates ordering based on category values for an axis.
 * Groups nodes by their category value (sorted alphabetically) then by their original order within each group.
 * @param {Object} viz_state - The visualization state
 * @param {string} axis - 'row' or 'col'
 * @param {number} attr_index - Index of the attribute to order by
 * @returns {Array<number>} Array of ordering indices
 */
const generate_category_order = (viz_state, axis, attr_index) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const attr_def = viz_state.attr.all_defs[axis]?.[attr_index];

  if (!attr_def || !attr_def.values) {
    return null;
  }

  // Get unique category values and sort them
  const { values } = attr_def;
  const unique_values = [
    ...new Set(values.filter((v) => v !== null && v !== undefined)),
  ];

  // Sort categories - for categorical, sort alphabetically; for numeric, sort by value
  if (attr_def.type === 'numeric') {
    unique_values.sort((a, b) => Number(a) - Number(b));
  } else {
    unique_values.sort();
  }

  // Create a map of category -> nodes with that category (preserving original order)
  const category_groups = new Map();
  unique_values.forEach((cat) => category_groups.set(cat, []));

  // Group nodes by category
  nodes.forEach((node, index) => {
    const cat_value = values[index];
    if (
      cat_value !== null &&
      cat_value !== undefined &&
      category_groups.has(cat_value)
    ) {
      category_groups.get(cat_value).push({ node, index });
    }
  });

  // Build the new order - nodes are ranked by their position in the sorted category groups
  // Order array: order[original_index] = new_rank
  const order = new Array(nodes.length).fill(0);
  let rank = 1;

  category_groups.forEach((group_nodes) => {
    // Sort within group by their clust order to maintain some structure
    group_nodes.sort((a, b) => a.node.clust - b.node.clust);
    group_nodes.forEach(({ index }) => {
      order[index] = rank++;
    });
  });

  return order;
};

/**
 * Handles reordering when an attribute label is double-clicked.
 * @param {Object} viz_state - The visualization state
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {string} axis - 'row' or 'col'
 * @param {number} attr_index - Index of the attribute
 * @param {string} attr_name - Name of the attribute
 */
const reorder_by_attribute = (
  viz_state,
  deck_mat,
  layers_mat,
  axis,
  attr_index,
  attr_name
) => {
  // Generate the order key name for this attribute
  const order_key = `attr_${attr_index}`;

  // Check if we already have this order computed
  if (!viz_state.mat.orders[axis][order_key]) {
    const new_order = generate_category_order(viz_state, axis, attr_index);
    if (new_order) {
      viz_state.mat.orders[axis][order_key] = new_order;
    }
  }

  // If order was generated successfully, apply it
  if (viz_state.mat.orders[axis][order_key]) {
    // Update current order
    viz_state.order.current[axis] = order_key;

    // Update obs_store if available
    if (viz_state.obs_store?.attr_reorder_state) {
      viz_state.obs_store.attr_reorder_state.set({
        axis,
        attr_index,
        attr_name,
        order_key,
      });
    }

    // Deselect all reorder buttons for this axis
    deselect_reorder_buttons(viz_state, axis);

    // Update layers
    layers_mat.mat_layer = layers_mat.mat_layer.clone({
      updateTriggers: {
        getPosition: [viz_state.order.current.row, viz_state.order.current.col],
      },
    });

    if (axis === 'row') {
      layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        updateTriggers: {
          getPosition: viz_state.order.current.row,
        },
      });
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        updateTriggers: {
          getPosition: viz_state.order.current.row,
        },
      });
    } else {
      layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        updateTriggers: {
          getPosition: viz_state.order.current.col,
        },
      });
      layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
        updateTriggers: {
          getPosition: viz_state.order.current.col,
        },
      });

      // Reordering columns can change which bar is leftmost, which can
      // change which row labels fit their segment (composition mode only).
      refresh_row_label_visibility(layers_mat, viz_state);
    }

    // Hide dendro when not in clust order
    toggle_dendro_layer_visibility(layers_mat, viz_state, axis);

    // Update the deck
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }
};

const DOUBLE_CLICK_DELAY = 250;

/**
 * Creates the data array for column attribute labels.
 * Each item represents one attribute label positioned at the right of the attribute bars.
 * @param {Object} viz_state - The visualization state
 * @returns {Array} Array of label data objects
 */
const get_col_attr_label_data = (viz_state) => {
  const attr_names = viz_state.attr.names.col || [];
  return attr_names.map((name, index) => ({
    name,
    index,
    axis: 'col',
  }));
};

/**
 * Creates the data array for row attribute labels.
 * Each item represents one attribute label positioned at the top of the attribute bars.
 * @param {Object} viz_state - The visualization state
 * @returns {Array} Array of label data objects
 */
const get_row_attr_label_data = (viz_state) => {
  const attr_names = viz_state.attr.names.row || [];
  return attr_names.map((name, index) => ({
    name,
    index,
    axis: 'row',
  }));
};

/**
 * Gets the position for a column attribute label.
 * Labels appear in a static view at the right side (aligned with dendrogram x position),
 * vertically aligned with each attribute bar.
 *
 * Column bars y position in cols view:
 * - Canvas y = col_cat_offset * (attr_index + 1.5) - 30 + cat_shift_col
 * - Cols view target.y = label_col_y (25)
 * - DOM y = col_region/2 + (canvas_y - 25)
 *
 * For col_attr_labels view with centered target (1:1 mapping):
 * - DOM y = canvas_y (since target is at center)
 * - So we need canvas_y = col_region/2 + (bar_canvas_y - label_col_y)
 *
 * @param {Object} d - The label data
 * @param {Object} viz_state - The visualization state
 * @returns {Array} [x, y] position
 */
const col_attr_label_get_position = (d, viz_state) => {
  // X position: at the left edge of the col_attr_labels view
  const pos_x = 5;

  // Y position: calculate to match the column bar's DOM position
  // Bar canvas y in cols view:
  const bar_canvas_y =
    viz_state.viz.col_cat_offset * (d.index + 1.5) -
    30 +
    viz_state.viz.cat_shift_col;

  // Convert to DOM y (cols view has target.y = label_col_y)
  // DOM y = col_region/2 + (bar_canvas_y - label_col_y)
  // For our centered view, canvas y = DOM y
  const pos_y =
    viz_state.viz.col_region / 2 + (bar_canvas_y - viz_state.viz.label_col_y);

  return [pos_x, pos_y];
};

/**
 * Gets the position for a row attribute label.
 * Labels appear at the top of the row_attr_labels view, aligned with each attribute bar column.
 * Text reads from bottom to top.
 *
 * Row bars x position formula from attr_state.js and cat_layers.js:
 * x = row_cat_offset * (attr_index + 0.5) + 20 + cat_shift_row
 * x = 9 * (attr_index + 0.5) + 20 + 30 = 9 * attr_index + 54.5
 *
 * @param {Object} d - The label data
 * @param {Object} viz_state - The visualization state
 * @returns {Array} [x, y] position
 */
const row_attr_label_get_position = (d, viz_state) => {
  // X position: match the row attribute bar x position
  // Formula: row_cat_offset * (attr_index + 0.5) + 20 + cat_shift_row
  const pos_x =
    viz_state.viz.row_cat_offset * (d.index + 0.5) +
    20 +
    viz_state.viz.cat_shift_row;

  // Y position: at the bottom of the view (just above where the rows view starts)
  // The rows view starts at y = col_region, so position labels just above that
  const pos_y = viz_state.viz.col_region - 5;

  return [pos_x, pos_y];
};

/**
 * Creates the deck.gl TextLayer for column attribute labels.
 * @param {Object} viz_state - The visualization state
 * @returns {TextLayer} The column attribute label layer
 */
export const ini_col_attr_label_layer = (viz_state) => {
  const data = get_col_attr_label_data(viz_state);

  if (data.length === 0) {
    return null;
  }

  const col_attr_label_layer = new TextLayer({
    id: 'col-attr-label-layer',
    data,
    getPosition: (d) => col_attr_label_get_position(d, viz_state),
    getText: (d) => d.name,
    getSize: 10,
    getColor: [80, 80, 80],
    getAngle: 0,
    getTextAnchor: 'start', // Text starts from left
    getAlignmentBaseline: 'center',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 1,
    pickable: true,
  });

  return col_attr_label_layer;
};

/**
 * Creates the deck.gl TextLayer for row attribute labels.
 * @param {Object} viz_state - The visualization state
 * @returns {TextLayer} The row attribute label layer
 */
export const ini_row_attr_label_layer = (viz_state) => {
  const data = get_row_attr_label_data(viz_state);

  if (data.length === 0) {
    return null;
  }

  const row_attr_label_layer = new TextLayer({
    id: 'row-attr-label-layer',
    data,
    getPosition: (d) => row_attr_label_get_position(d, viz_state),
    getText: (d) => d.name,
    getSize: 10,
    getColor: [80, 80, 80],
    getAngle: 90, // Rotated so text reads bottom-to-top
    getTextAnchor: 'start', // Text starts from the bottom
    getAlignmentBaseline: 'center',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 1,
    pickable: true,
  });

  return row_attr_label_layer;
};

/**
 * Click handler for column attribute labels (double-click to reorder).
 * @param {Object} event - The click event
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {Object} viz_state - The visualization state
 */
const col_attr_label_onclick = (event, deck_mat, layers_mat, viz_state) => {
  viz_state.labels.clicks.col_attr =
    (viz_state.labels.clicks.col_attr || 0) + 1;

  if (viz_state.labels.clicks.col_attr === 1) {
    setTimeout(() => {
      viz_state.labels.clicks.col_attr = 0;
    }, DOUBLE_CLICK_DELAY);
  } else if (viz_state.labels.clicks.col_attr === 2) {
    viz_state.labels.clicks.col_attr = 0;
    reorder_by_attribute(
      viz_state,
      deck_mat,
      layers_mat,
      'col',
      event.object.index,
      event.object.name
    );
  }
};

/**
 * Click handler for row attribute labels (double-click to reorder).
 * @param {Object} event - The click event
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {Object} viz_state - The visualization state
 */
const row_attr_label_onclick = (event, deck_mat, layers_mat, viz_state) => {
  viz_state.labels.clicks.row_attr =
    (viz_state.labels.clicks.row_attr || 0) + 1;

  if (viz_state.labels.clicks.row_attr === 1) {
    setTimeout(() => {
      viz_state.labels.clicks.row_attr = 0;
    }, DOUBLE_CLICK_DELAY);
  } else if (viz_state.labels.clicks.row_attr === 2) {
    viz_state.labels.clicks.row_attr = 0;
    reorder_by_attribute(
      viz_state,
      deck_mat,
      layers_mat,
      'row',
      event.object.index,
      event.object.name
    );
  }
};

/**
 * Sets up the click handler for the column attribute label layer.
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {Object} viz_state - The visualization state
 */
export const set_col_attr_label_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  if (!layers_mat.col_attr_label_layer) return;

  layers_mat.col_attr_label_layer = layers_mat.col_attr_label_layer.clone({
    onClick: (event) =>
      col_attr_label_onclick(event, deck_mat, layers_mat, viz_state),
  });
};

/**
 * Sets up the click handler for the row attribute label layer.
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {Object} viz_state - The visualization state
 */
export const set_row_attr_label_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  if (!layers_mat.row_attr_label_layer) return;

  layers_mat.row_attr_label_layer = layers_mat.row_attr_label_layer.clone({
    onClick: (event) =>
      row_attr_label_onclick(event, deck_mat, layers_mat, viz_state),
  });
};

/**
 * Refreshes the attribute label layers with current attribute definitions.
 * Call this after manual categories are added/changed.
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {Object} viz_state - The visualization state
 */
export const refresh_attr_label_layers = (deck_mat, layers_mat, viz_state) => {
  // Update col attribute labels
  const col_data = get_col_attr_label_data(viz_state);
  if (layers_mat.col_attr_label_layer && col_data.length > 0) {
    layers_mat.col_attr_label_layer = layers_mat.col_attr_label_layer.clone({
      data: col_data,
    });
  } else if (col_data.length > 0) {
    layers_mat.col_attr_label_layer = ini_col_attr_label_layer(viz_state);
    set_col_attr_label_layer_onclick(deck_mat, layers_mat, viz_state);
  }

  // Update row attribute labels
  const row_data = get_row_attr_label_data(viz_state);
  if (layers_mat.row_attr_label_layer && row_data.length > 0) {
    layers_mat.row_attr_label_layer = layers_mat.row_attr_label_layer.clone({
      data: row_data,
    });
  } else if (row_data.length > 0) {
    layers_mat.row_attr_label_layer = ini_row_attr_label_layer(viz_state);
    set_row_attr_label_layer_onclick(deck_mat, layers_mat, viz_state);
  }

  // Update deck
  deck_mat.setProps({
    layers: get_mat_layers_list(layers_mat),
  });
};

/**
 * Initializes the attribute label layers and adds them to layers_mat.
 * @param {Object} deck_mat - The deck.gl instance
 * @param {Object} layers_mat - The layers object
 * @param {Object} viz_state - The visualization state
 */
export const initialize_attribute_labels = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  // Create col attribute label layer
  layers_mat.col_attr_label_layer = ini_col_attr_label_layer(viz_state);
  if (layers_mat.col_attr_label_layer) {
    set_col_attr_label_layer_onclick(deck_mat, layers_mat, viz_state);
  }

  // Create row attribute label layer
  layers_mat.row_attr_label_layer = ini_row_attr_label_layer(viz_state);
  if (layers_mat.row_attr_label_layer) {
    set_row_attr_label_layer_onclick(deck_mat, layers_mat, viz_state);
  }

  // Subscribe to manual category changes to refresh labels
  if (viz_state.obs_store?.manual_cat) {
    ['row', 'col'].forEach((axis) => {
      const manual_store = viz_state.obs_store.manual_cat[axis];
      if (manual_store) {
        manual_store.subscribe(
          () => {
            // Delay refresh slightly to allow attribute definitions to update
            setTimeout(() => {
              refresh_attr_label_layers(deck_mat, layers_mat, viz_state);
            }, 150);
          },
          { immediate: false }
        );
      }
    });
  }
};
