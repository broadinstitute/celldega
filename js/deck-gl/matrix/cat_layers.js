import * as d3 from 'd3';

import {
  crop_fade_axis_alpha_factor,
  crop_fade_signature,
  crop_filter_signature,
  filter_cat_data,
  get_axis_center_position,
  get_axis_slot_size,
  is_axis_index_visible,
} from '../../matrix/crop_filter';

import { CustomMatrixLayer } from './custom_matrix_layer';
import { get_mat_layers_list } from './matrix_layers';

const get_layer_update_triggers = (layer) => layer?.props?.updateTriggers || {};

const cat_fill_trigger = (viz_state, hovered = viz_state.hovered_cat) => [
  crop_filter_signature(viz_state),
  crop_fade_signature(viz_state),
  hovered,
];

/**
 * Get the fill color for a category tile, with hover highlighting support.
 * When hovering over a category value:
 * - Matching tiles (same category value) stay at normal opacity
 * - ALL other tiles (any axis, any attribute) become very transparent
 */
const getCatFillColor = (d, viz_state, _axis) => {
  const hovered = viz_state.hovered_cat;
  const crop_factor = crop_fade_axis_alpha_factor(
    viz_state,
    _axis,
    d.original_index
  );

  const apply_crop_fade = (color) => [
    color[0],
    color[1],
    color[2],
    Math.round((color[3] ?? 255) * crop_factor),
  ];

  // If nothing is hovered, return normal color
  if (!hovered || !hovered.name) {
    return crop_factor === 1 ? d.color : apply_crop_fade(d.color);
  }

  // If this tile matches the hovered category VALUE (regardless of axis or attribute level)
  // Keep it at normal opacity
  if (d.name === hovered.name) {
    return crop_factor === 1 ? d.color : apply_crop_fade(d.color);
  }

  // Otherwise, make this tile very transparent so the hovered category stands out
  const [r, g, b] = d.color.slice(0, 3);
  return [r, g, b, Math.round(40 * crop_factor)]; // Very low alpha
};

/**
 * Handle category tile click - track entity, attribute, and value.
 */
const cat_layer_onclick = (event, viz_state, axis) => {
  const attr_index = event.object?.level;
  const node_index = event.object?.original_index;
  const value = event.object?.name;

  if (attr_index === undefined || node_index === undefined) return;

  const attr_name = viz_state.attr.names[axis]?.[attr_index];
  if (!attr_name) return;

  const node_name =
    axis === 'row'
      ? viz_state.row_nodes[node_index].name
      : viz_state.col_nodes[node_index].name;

  // Get all nodes with the same category value for this attribute
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const cat_key = `cat-${attr_index}`;
  const matching_nodes = nodes
    .filter(
      (node, index) =>
        node[cat_key] === value && is_axis_index_visible(viz_state, axis, index)
    )
    .map((node) => node.name);

  // Get entity info for this axis
  const axis_entity =
    axis === 'row' ? viz_state.row_entity : viz_state.col_entity;

  // Set click info
  viz_state.click.type = 'cat_value';
  viz_state.click.value = {
    axis,
    attr_name,
    attr_index,
    value,
    node_name,
    node_names: matching_nodes,
    entity: axis_entity.entity,
    attr: axis_entity.attr,
    row_entity_full: viz_state.row_entity,
    col_entity_full: viz_state.col_entity,
  };

  // Update the clustergram store
  if (viz_state.obs_store?.selected_category) {
    const current = viz_state.obs_store.selected_category.get();
    // Toggle selection if clicking the same category
    if (
      current &&
      current.axis === axis &&
      current.attr_index === attr_index &&
      current.value === value
    ) {
      viz_state.obs_store.selected_category.set(null);
    } else {
      viz_state.obs_store.selected_category.set({
        axis,
        attr_name,
        attr_index,
        value,
        node_names: matching_nodes,
      });
    }
  }

  if (viz_state.model?.set) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }
};

// Hover must dwell this long before a category tile's cross-matrix highlight
// kicks in, matching every other hover-highlight in the widget (composition
// bars/labels, dendrogram trapezoids) for a consistent feel; leaving a tile
// clears instantly.
const CAT_HOVER_DELAY_MS = 250;

const apply_cat_hover = (deck_mat, layers_mat, viz_state, hovered) => {
  const prev_hovered = viz_state.hovered_cat;
  if (
    prev_hovered?.axis === hovered?.axis &&
    prev_hovered?.level === hovered?.level &&
    prev_hovered?.name === hovered?.name
  ) {
    return;
  }

  viz_state.hovered_cat = hovered;

  // Trigger re-render of both cat layers to update transparency
  layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.row_cat_layer),
      getFillColor: cat_fill_trigger(viz_state, hovered),
    },
  });
  layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.col_cat_layer),
      getFillColor: cat_fill_trigger(viz_state, hovered),
    },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });

  // Also update obs_store for other listeners
  if (viz_state.obs_store?.hovered_category) {
    const attr_name = hovered
      ? viz_state.attr.names[hovered.axis]?.[hovered.level]
      : null;
    viz_state.obs_store.hovered_category.set(
      hovered
        ? {
            axis: hovered.axis,
            attr_name,
            attr_index: hovered.level,
            value: hovered.name,
          }
        : null
    );
  }
};

/**
 * Handle category tile hover - for highlighting.
 * Updates viz_state.hovered_cat and triggers layer re-render.
 */
const cat_layer_onhover = (info, viz_state, axis, deck_mat, layers_mat) => {
  clearTimeout(viz_state._cat_hover_timer);

  if (!info.object) {
    // Mouse left the tile - clear hover state immediately.
    apply_cat_hover(deck_mat, layers_mat, viz_state, null);
    return;
  }

  const attr_index = info.object?.level;
  const value = info.object?.name;

  if (attr_index === undefined || value === undefined) return;

  const hovered = { axis, name: value, level: attr_index };
  const prev_hovered = viz_state.hovered_cat;

  // Already hovering this exact tile (highlight already applied) - no-op.
  if (
    prev_hovered?.axis === hovered.axis &&
    prev_hovered?.level === hovered.level &&
    prev_hovered?.name === hovered.name
  ) {
    return;
  }

  viz_state._cat_hover_timer = setTimeout(() => {
    apply_cat_hover(deck_mat, layers_mat, viz_state, hovered);
  }, CAT_HOVER_DELAY_MS);
};

/**
 * Force-clear the categorical attribute hover highlight, cancelling any
 * pending delayed-highlight timer first. See `clear_composition_hover` /
 * `clear_dendro_hover` for why cancelling the timer (not just clearing
 * current state) matters. Safe to call unconditionally.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const clear_cat_hover = (deck_mat, layers_mat, viz_state) => {
  clearTimeout(viz_state._cat_hover_timer);
  apply_cat_hover(deck_mat, layers_mat, viz_state, null);
};

export const ini_row_cat_layer = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const row_cat_layer = new CustomMatrixLayer({
    id: 'row-layer',
    data: filter_cat_data(viz_state, 'row'),
    getPosition: (d) => {
      return [
        d.position[0] + viz_state.viz.cat_shift_row,
        get_axis_center_position(viz_state, 'row', d.original_index) ?? 0,
      ];
    },
    getFillColor: (d) => getCatFillColor(d, viz_state, 'row'),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
    transitions,
    opacity: 0.8,
    tile_width: (viz_state.viz.row_cat_width / 2) * 0.9,
    tile_height: get_axis_slot_size(viz_state, 'row') * 0.5,
    updateTriggers: {
      getPosition: crop_sig,
      getFillColor: cat_fill_trigger(viz_state),
    },
  });

  return row_cat_layer;
};

export const ini_col_cat_layer = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const col_cat_layer = new CustomMatrixLayer({
    id: 'col-layer',
    data: filter_cat_data(viz_state, 'col'),
    getPosition: (d) => {
      return [
        get_axis_center_position(viz_state, 'col', d.original_index) ?? 0,
        d.position[1] + viz_state.viz.cat_shift_col,
      ];
    },
    getFillColor: (d) => getCatFillColor(d, viz_state, 'col'),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
    transitions,
    opacity: 0.8,
    tile_width: get_axis_slot_size(viz_state, 'col') * 0.5,
    tile_height: viz_state.viz.col_cat_height / 2,
    updateTriggers: {
      getPosition: crop_sig,
      getFillColor: cat_fill_trigger(viz_state),
    },
  });

  return col_cat_layer;
};

/**
 * Set up click and hover handlers for category layers.
 */
export const set_cat_layer_handlers = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  const layer_key = `${axis}_cat_layer`;

  layers_mat[layer_key] = layers_mat[layer_key].clone({
    onClick: (event) => {
      // First check if editor is open (existing behavior)
      if (viz_state.attr?.editor?.open) {
        const attr_index = event.object?.level;
        const node_index = event.object?.original_index;
        if (attr_index === undefined || node_index === undefined) return;

        const attr_name = viz_state.attr.names[axis]?.[attr_index];
        if (!attr_name) return;

        const node_name =
          axis === 'row'
            ? viz_state.row_nodes[node_index].name
            : viz_state.col_nodes[node_index].name;

        const attr_def = viz_state.attr.all_defs?.[axis]?.[attr_index];
        const value = event.object?.name;
        const color_key =
          value === null || value === undefined ? null : String(value);
        const color_hex = attr_def?.color_map?.[color_key] || null;

        viz_state.attr.editor.open({
          axis,
          selection: [node_name],
          attribute_name: attr_name,
          initial_value: value,
          initial_color: color_hex,
          position: event?.pixel
            ? { x: event.pixel[0], y: event.pixel[1] }
            : undefined,
        });
      } else {
        // Normal click behavior - track selection
        cat_layer_onclick(event, viz_state, axis);
      }
    },
    onHover: (info) =>
      cat_layer_onhover(info, viz_state, axis, deck_mat, layers_mat),
  });
};
