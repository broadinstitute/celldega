import { PolygonLayer } from 'deck.gl';

import {
  sync_selected_genes,
  sync_selected_rows,
  sync_selected_cols,
} from '../../global_variables/selected_genes';

import { get_mat_layers_list } from './matrix_layers';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const FOCUSED_FILL_COLOR = [0, 0, 0, 180];

const get_current_focus = (viz_state) => {
  const store_focus =
    viz_state?.obs_store?.focused_dendro &&
    typeof viz_state.obs_store.focused_dendro.get === 'function'
      ? viz_state.obs_store.focused_dendro.get()
      : null;

  return store_focus ?? viz_state.dendro?.active_polygon ?? null;
};

const apply_dendro_focus = (deck_mat, layers_mat, viz_state, focus) => {
  const normalized_focus = focus
    ? { axis: focus.axis, name: focus.name }
    : null;

  let did_update = false;

  DENDRO_AXES.forEach((targetAxis) => {
    if (!viz_state.dendro.polygons[targetAxis]) {
      return;
    }

    const updated_polygons = viz_state.dendro.polygons[targetAxis].map(
      (polygon) => {
        const is_focused =
          !!normalized_focus &&
          polygon.properties.axis === normalized_focus.axis &&
          polygon.properties.name === normalized_focus.name;

        if (polygon.properties.is_focused === is_focused) {
          return polygon;
        }

        did_update = true;

        return {
          ...polygon,
          properties: {
            ...polygon.properties,
            is_focused,
          },
        };
      }
    );

    viz_state.dendro.polygons[targetAxis] = updated_polygons;

    if (layers_mat[`${targetAxis}_dendro_layer`]) {
      layers_mat[`${targetAxis}_dendro_layer`] = layers_mat[
        `${targetAxis}_dendro_layer`
      ].clone({
        data: updated_polygons,
      });
    }
  });

  viz_state.dendro.active_polygon = normalized_focus;

  if (viz_state.obs_store?.focused_dendro) {
    const focus_value = normalized_focus ? { ...normalized_focus } : null;
    viz_state.obs_store.focused_dendro.set(focus_value);
  }

  if (did_update && typeof deck_mat?.setProps === 'function') {
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }
};

export const ini_dendro_layer = (layers_mat, viz_state, axis) => {
  const inst_layer = new PolygonLayer({
    id: `${axis}-dendro-layer`,
    data: viz_state.dendro.polygons[axis],
    getPolygon: (d) => d.coordinates,
    getFillColor: (d) => {
      if (d.properties.is_focused) {
        return FOCUSED_FILL_COLOR;
      }

      if (Array.isArray(d.properties.fill_color)) {
        return d.properties.fill_color;
      }

      return DEFAULT_FILL_COLOR;
    },
    getLineColor: [255, 255, 255, 255],
    lineWidthMinPixels: 0,
    pickable: true,
    antialiasing: false,
    // autoHighlight: true, // Highlight on hover
    // onHover: ({ object }) => console.log(object?.properties.name), // Hover info
  });

  return inst_layer;
};

export const update_dendro_layer_data = (layers_mat, viz_state, axis) => {
  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      data: viz_state.dendro.polygons[axis],
    }
  );
};

export const toggle_dendro_layer_visibility = (layers_mat, viz_state, axis) => {
  // if viz_state.order.curent[axis] is 'clust' then the dendrogram is visible
  let is_visible = false;
  if (viz_state.order.current[axis] === 'clust') {
    is_visible = true;
  }

  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      // visible: !layers_mat[axis + '_dendro_layer'].visible,
      visible: is_visible,
    }
  );
};

const focus_dendro_polygon = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygonName
) => {
  const previous_focus = get_current_focus(viz_state);

  if (
    previous_focus &&
    previous_focus.axis === axis &&
    previous_focus.name === polygonName
  ) {
    apply_dendro_focus(deck_mat, layers_mat, viz_state, null);
    return;
  }

  apply_dendro_focus(deck_mat, layers_mat, viz_state, {
    axis,
    name: polygonName,
  });
};

/**
 * Compute category breakdown for selected nodes.
 * Returns an object with category counts for each attribute.
 */
const compute_category_breakdown = (viz_state, axis, selected_names) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const attr_names = viz_state.attr?.names?.[axis] || [];

  // Find the selected node indices
  const selected_set = new Set(selected_names);
  const selected_nodes = nodes.filter((node) => selected_set.has(node.name));

  const breakdown = {};

  // For each attribute, count the category values
  attr_names.forEach((attr_name, attr_index) => {
    const cat_key = `cat-${attr_index}`;
    const counts = {};

    selected_nodes.forEach((node) => {
      const value = node[cat_key];
      if (value !== undefined && value !== null) {
        counts[value] = (counts[value] || 0) + 1;
      }
    });

    // Convert to array sorted by count
    const breakdown_array = Object.entries(counts)
      .map(([name, count]) => ({ name, value: count }))
      .sort((a, b) => b.value - a.value);

    if (breakdown_array.length > 0) {
      breakdown[attr_name] = breakdown_array;
    }
  });

  return breakdown;
};

const dendro_layer_onclick = (event, deck_mat, layers_mat, viz_state, axis) => {
  viz_state.click.type = `${axis}_dendro`;

  // Get the entity info for the clicked axis
  const axis_entity =
    axis === 'row' ? viz_state.row_entity : viz_state.col_entity;
  const selected_names = event.object.properties.all_names || [];

  viz_state.click.value = {
    name: event.object.properties.name,
    selected_names,
    // New structured entity info for the clicked axis
    entity: axis_entity.entity,
    attr: axis_entity.attr,
    // Legacy fields for backwards compatibility
    row_entity: viz_state.row_entity.entity,
    col_entity: viz_state.col_entity.entity,
    // Full entity info for both axes (for advanced use cases)
    row_entity_full: viz_state.row_entity,
    col_entity_full: viz_state.col_entity,
  };

  focus_dendro_polygon(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    event.object.properties.name
  );

  // Update dendro_selection in the store
  let is_unselecting = false;
  if (viz_state.obs_store?.dendro_selection) {
    const current = viz_state.obs_store.dendro_selection.get();
    // Toggle off if clicking the same dendro
    if (
      current &&
      current.axis === axis &&
      current.name === event.object.properties.name
    ) {
      is_unselecting = true;
      viz_state.obs_store.dendro_selection.set(null);
      // Reset category breakdown
      if (viz_state.obs_store?.category_breakdown) {
        viz_state.obs_store.category_breakdown.set({ row: {}, col: {} });
      }
    } else {
      viz_state.obs_store.dendro_selection.set({
        axis,
        name: event.object.properties.name,
        selected_names,
      });

      // Compute and update category breakdown
      if (viz_state.obs_store?.category_breakdown) {
        const breakdown = compute_category_breakdown(
          viz_state,
          axis,
          selected_names
        );
        const current_breakdown =
          viz_state.obs_store.category_breakdown.get() || { row: {}, col: {} };
        viz_state.obs_store.category_breakdown.set({
          ...current_breakdown,
          [axis]: breakdown,
        });
      }
    }
  }

  // If unselecting, update click_info with empty selected_names
  // so the Landscape handler knows to clear the cells
  if (is_unselecting) {
    viz_state.click.value.selected_names = [];
    viz_state.click.value.is_unselecting = true;

    // Close the editor when unselecting
    if (viz_state.attr?.editor?.close) {
      viz_state.attr.editor.close();
    }
  }

  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  // Sync selected rows/cols to Python model
  // If unselecting, clear the selections
  const names_to_sync = is_unselecting ? [] : selected_names;

  if (axis === 'row') {
    sync_selected_rows(viz_state, names_to_sync);
    // Also sync to selected_genes for backwards compatibility
    sync_selected_genes(viz_state, names_to_sync);
  } else if (axis === 'col') {
    sync_selected_cols(viz_state, names_to_sync);
  }

  // Open editor positioned 1px left of row dendro or 1px above col dendro
  if (viz_state.attr?.editor?.open && !is_unselecting) {
    const editor_width = 240;
    const editor_height = 200;
    let position;
    if (axis === 'row') {
      // Row dendro is on the right - position editor 1px to the left of it
      position = {
        x:
          (viz_state.viz.row_region || 0) +
          (viz_state.viz.label_buffer || 0) +
          (viz_state.viz.mat_width || 300) -
          editor_width -
          1,
        y: (viz_state.viz.col_region || 0) + (viz_state.viz.label_buffer || 0),
      };
    } else {
      // Col dendro is at the bottom - position editor 1px above it
      position = {
        x:
          (viz_state.viz.row_region || 0) +
          (viz_state.viz.label_buffer || 0) +
          (viz_state.viz.mat_width || 300) -
          editor_width,
        y:
          (viz_state.viz.col_region || 0) +
          (viz_state.viz.label_buffer || 0) +
          (viz_state.viz.mat_height || 300) -
          editor_height -
          1,
      };
    }
    viz_state.attr.editor.open({
      axis,
      selection: selected_names,
      position,
    });
  }

  if (typeof viz_state.custom_callbacks[`${axis}_dendro`] === 'function') {
    viz_state.custom_callbacks[`${axis}_dendro`](selected_names);
  }
};

export const set_dendro_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      onClick: (event) =>
        dendro_layer_onclick(event, deck_mat, layers_mat, viz_state, axis),
    }
  );
};
