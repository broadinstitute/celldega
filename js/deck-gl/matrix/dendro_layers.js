import { PolygonLayer } from 'deck.gl';

import { sync_selected_genes } from '../../global_variables/selected_genes';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const DIMMED_FILL_COLOR = [160, 160, 160, 25];

const getCurrentFocus = (viz_state) => {
  const storeFocus =
    viz_state?.obs_store?.focused_dendro &&
    typeof viz_state.obs_store.focused_dendro.get === 'function'
      ? viz_state.obs_store.focused_dendro.get()
      : null;

  return storeFocus ?? viz_state.dendro?.active_polygon ?? null;
};

const applyDendroFocus = (layers_mat, viz_state, focus) => {
  const normalizedFocus = focus
    ? { axis: focus.axis, name: focus.name }
    : null;

  DENDRO_AXES.forEach((targetAxis) => {
    if (!viz_state.dendro.polygons[targetAxis]) {
      return;
    }

    const updatedPolygons = viz_state.dendro.polygons[targetAxis].map(
      (polygon) => {
        const isFocused =
          !!normalizedFocus &&
          polygon.properties.axis === normalizedFocus.axis &&
          polygon.properties.name === normalizedFocus.name;

        if (polygon.properties.is_focused === isFocused) {
          return polygon;
        }

        return {
          ...polygon,
          properties: {
            ...polygon.properties,
            is_focused: isFocused,
          },
        };
      }
    );

    viz_state.dendro.polygons[targetAxis] = updatedPolygons;

    if (layers_mat[`${targetAxis}_dendro_layer`]) {
      layers_mat[`${targetAxis}_dendro_layer`] =
        layers_mat[`${targetAxis}_dendro_layer`].clone({
          data: updatedPolygons,
        });
    }
  });

  viz_state.dendro.active_polygon = normalizedFocus;

  if (viz_state.obs_store?.focused_dendro) {
    const focusValue = normalizedFocus
      ? { ...normalizedFocus }
      : null;
    viz_state.obs_store.focused_dendro.set(focusValue);
  }
};

export const ini_dendro_layer = (layers_mat, viz_state, axis) => {
  const inst_layer = new PolygonLayer({
    id: `${axis}-dendro-layer`,
    data: viz_state.dendro.polygons[axis],
    getPolygon: (d) => d.coordinates,
    getFillColor: (d) => {
      const currentFocus = getCurrentFocus(viz_state);

      if (
        currentFocus &&
        d.properties.axis === currentFocus.axis &&
        d.properties.name === currentFocus.name
      ) {
        return DEFAULT_FILL_COLOR;
      }

      return currentFocus ? DIMMED_FILL_COLOR : DEFAULT_FILL_COLOR;
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

const focus_dendro_polygon = (layers_mat, viz_state, axis, polygonName) => {
  const previousFocus = getCurrentFocus(viz_state);

  if (
    previousFocus &&
    previousFocus.axis === axis &&
    previousFocus.name === polygonName
  ) {
    return;
  }

  applyDendroFocus(layers_mat, viz_state, { axis, name: polygonName });
};

const dendro_layer_onclick = (event, deck_mat, layers_mat, viz_state, axis) => {
  viz_state.click.type = `${axis}_dendro`;

  viz_state.click.value = {
    name: event.object.properties.name,
    selected_names: event.object.properties.all_names,
  };

  focus_dendro_polygon(layers_mat, viz_state, axis, event.object.properties.name);

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  if (axis === 'row') {
    sync_selected_genes(viz_state, event.object.properties.all_names);
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
