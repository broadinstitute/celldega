import * as d3 from 'd3';

import { CustomMatrixLayer } from './custom_matrix_layer';
import { get_mat_layers_list } from './matrix_layers';

/**
 * Get the fill color for a category tile, with hover highlighting support.
 * When hovering over a category value:
 * - Matching tiles (same category value) stay at normal opacity
 * - ALL other tiles (any axis, any attribute) become very transparent
 */
const getCatFillColor = (d, viz_state, _axis) => {
  const hovered = viz_state.hovered_cat;

  // If nothing is hovered, return normal color
  if (!hovered || !hovered.name) {
    return d.color;
  }

  // If this tile matches the hovered category VALUE (regardless of axis or attribute level)
  // Keep it at normal opacity
  if (d.name === hovered.name) {
    return d.color;
  }

  // Otherwise, make this tile very transparent so the hovered category stands out
  const [r, g, b] = d.color.slice(0, 3);
  return [r, g, b, 40]; // Very low alpha
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
    .filter((node) => node[cat_key] === value)
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

/**
 * Handle category tile hover - for highlighting.
 * Updates viz_state.hovered_cat and triggers layer re-render.
 */
const cat_layer_onhover = (info, viz_state, axis, deck_mat, layers_mat) => {
  const prev_hovered = viz_state.hovered_cat;

  if (!info.object) {
    // Mouse left the tile - clear hover state
    if (prev_hovered) {
      viz_state.hovered_cat = null;

      // Trigger re-render of both cat layers to restore normal colors
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        updateTriggers: {
          getFillColor: [null],
        },
      });
      layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
        updateTriggers: {
          getFillColor: [null],
        },
      });
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });

      // Clear obs_store hovered_category so bar graphs update
      if (viz_state.obs_store?.hovered_category) {
        viz_state.obs_store.hovered_category.set(null);
      }
    }
    return;
  }

  const attr_index = info.object?.level;
  const value = info.object?.name;

  if (attr_index === undefined || value === undefined) return;

  // Check if already hovering this exact tile
  if (
    prev_hovered?.axis === axis &&
    prev_hovered?.level === attr_index &&
    prev_hovered?.name === value
  ) {
    return; // Already hovering this tile
  }

  // Set new hover state
  viz_state.hovered_cat = {
    axis,
    name: value,
    level: attr_index,
  };

  // Trigger re-render of both cat layers to update transparency
  layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
    updateTriggers: {
      getFillColor: [viz_state.hovered_cat],
    },
  });
  layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
    updateTriggers: {
      getFillColor: [viz_state.hovered_cat],
    },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });

  // Also update obs_store for other listeners
  if (viz_state.obs_store?.hovered_category) {
    const attr_name = viz_state.attr.names[axis]?.[attr_index];
    viz_state.obs_store.hovered_category.set({
      axis,
      attr_name,
      attr_index,
      value,
    });
  }
};

export const ini_row_cat_layer = (viz_state) => {
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const row_cat_layer = new CustomMatrixLayer({
    id: 'row-layer',
    data: viz_state.cats.row_cat_data,
    getPosition: (d) => {
      const row_order = viz_state.mat.orders.row[viz_state.order.current.row];

      // Use original_index to look up its rank
      const clustered_index =
        viz_state.mat.num_rows - row_order[d.original_index];

      return [
        d.position[0] + viz_state.viz.cat_shift_row,
        viz_state.viz.row_offset * (clustered_index + 1.5),
      ];
    },
    getFillColor: (d) => getCatFillColor(d, viz_state, 'row'),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
    transitions,
    opacity: 0.8,
    tile_width: (viz_state.viz.row_cat_width / 2) * 0.9,
    tile_height: (viz_state.viz.mat_height / viz_state.mat.num_rows) * 0.5,
  });

  return row_cat_layer;
};

export const ini_col_cat_layer = (viz_state) => {
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const col_cat_layer = new CustomMatrixLayer({
    id: 'col-layer',
    data: viz_state.cats.col_cat_data,
    getPosition: (d) => {
      const col_order = viz_state.mat.orders.col[viz_state.order.current.col];

      // Use original_index to look up its rank
      const clustered_index =
        viz_state.mat.num_cols - col_order[d.original_index];

      return [
        viz_state.viz.col_offset * (clustered_index + 0.5),
        d.position[1] + viz_state.viz.cat_shift_col,
      ];
    },
    getFillColor: (d) => getCatFillColor(d, viz_state, 'col'),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
    transitions,
    opacity: 0.8,
    tile_width: (viz_state.viz.mat_width / viz_state.mat.num_cols) * 0.5,
    tile_height: viz_state.viz.col_cat_height / 2,
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
