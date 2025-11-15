import { PolygonLayer } from 'deck.gl';

import { sync_selected_genes } from '../../global_variables/selected_genes';

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
  const normalized_focus = focus ? { axis: focus.axis, name: focus.name } : null;

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
            is_focused: is_focused,
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

const dendro_layer_onclick = (event, deck_mat, layers_mat, viz_state, axis) => {
  viz_state.click.type = `${axis}_dendro`;

  viz_state.click.value = {
    name: event.object.properties.name,
    selected_names: event.object.properties.all_names,
  };

  focus_dendro_polygon(
    deck_mat,
    layers_mat,
    viz_state,
    axis,
    event.object.properties.name
  );

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  if (axis === 'row') {
    sync_selected_genes(viz_state, event.object.properties.all_names);
  }

  if (viz_state.attr?.editor?.open) {
    viz_state.attr.editor.open({
      axis,
      selection: event.object.properties.all_names || [],
      position: event?.pixel
        ? { x: event.pixel[0], y: event.pixel[1] }
        : undefined,
    });
  }

  if (typeof viz_state.custom_callbacks[`${axis}_dendro`] === 'function') {
    viz_state.custom_callbacks[`${axis}_dendro`](
      event.object.properties.all_names
    );
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
