import { LinearInterpolator, PolygonLayer } from 'deck.gl';

import { sync_selected_genes } from '../../global_variables/selected_genes';

import { curate_pan_x, curate_pan_y } from './curate_pan';
import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { update_zoom_data } from './zoom';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const FOCUSED_FILL_COLOR = [0, 0, 0, 180];
const DOUBLE_CLICK_DELAY = 250;
const DENDRO_FOCUS_TRANSITION = 650;
const MAX_FOCUS_ZOOM = 7;

const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

const ensureClickTracking = (viz_state) => {
  if (!viz_state.dendro.clicks) {
    viz_state.dendro.clicks = { row: 0, col: 0 };
  }

  if (!viz_state.dendro.clickTimeouts) {
    viz_state.dendro.clickTimeouts = { row: null, col: null };
  }
};

const applyViewStateTransition = (viewState) => {
  const transitionProps = () => ({
    transitionDuration: DENDRO_FOCUS_TRANSITION,
    transitionEasing: easeOutCubic,
    transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
  });

  return Object.fromEntries(
    Object.entries(viewState).map(([key, value]) => [
      key,
      { ...value, ...transitionProps() },
    ])
  );
};

const computeClusterZoom = (matrixSpan, clusterSpan, minUnit) => {
  const effectiveSpan = Math.min(matrixSpan, Math.max(clusterSpan, minUnit));

  const zoom = Math.log2(matrixSpan / Math.max(effectiveSpan, 1e-6));

  return Math.min(Math.max(zoom, 0), MAX_FOCUS_ZOOM);
};

const animate_focus_to_cluster = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygonProps
) => {
  if (!polygonProps) {
    return;
  }

  const isRowAxis = axis === 'row';
  const matrixSpan = isRowAxis
    ? viz_state.viz.mat_height
    : viz_state.viz.mat_width;
  const minUnit = isRowAxis
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;

  const currentZoomX = viz_state.zoom.zoom_data.matrix.zoom_x;
  const currentZoomY = viz_state.zoom.zoom_data.matrix.zoom_y;

  const clusterSpan = Math.max(
    Math.abs((polygonProps.pos_bot ?? 0) - (polygonProps.pos_top ?? 0)),
    minUnit
  );

  const targetZoom = computeClusterZoom(matrixSpan, clusterSpan, minUnit);

  const zoom_curated = [
    isRowAxis ? currentZoomX : targetZoom,
    isRowAxis ? targetZoom : currentZoomY,
  ];

  const clusterCenter =
    ((polygonProps.pos_top ?? 0) + (polygonProps.pos_bot ?? 0)) / 2;

  const existingPan = viz_state.zoom.zoom_data.matrix;

  const desiredPan = {
    x: isRowAxis ? existingPan.pan_x : clusterCenter,
    y: isRowAxis ? clusterCenter : existingPan.pan_y,
  };

  const pan_curated = [
    curate_pan_x(desiredPan.x, zoom_curated[0], viz_state),
    curate_pan_y(desiredPan.y, zoom_curated[1], viz_state),
  ];

  const viewId = isRowAxis ? 'dendro_rows' : 'dendro_cols';

  const globalViewState = redefine_global_view_state(
    viz_state,
    viewId,
    zoom_curated,
    pan_curated
  );

  update_zoom_data(viz_state, viewId, zoom_curated, pan_curated);

  viz_state.zoom.zoom_data.total_zoom.x = zoom_curated[0];
  viz_state.zoom.zoom_data.total_zoom.y = zoom_curated[1];

  deck_mat.setProps({
    viewState: applyViewStateTransition(globalViewState),
    layers: get_mat_layers_list(layers_mat),
  });
};

const getCurrentFocus = (viz_state) => {
  const storeFocus =
    viz_state?.obs_store?.focused_dendro &&
    typeof viz_state.obs_store.focused_dendro.get === 'function'
      ? viz_state.obs_store.focused_dendro.get()
      : null;

  return storeFocus ?? viz_state.dendro?.active_polygon ?? null;
};

const applyDendroFocus = (deck_mat, layers_mat, viz_state, focus) => {
  const normalizedFocus = focus ? { axis: focus.axis, name: focus.name } : null;

  let didUpdate = false;

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

        didUpdate = true;

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
      layers_mat[`${targetAxis}_dendro_layer`] = layers_mat[
        `${targetAxis}_dendro_layer`
      ].clone({
        data: updatedPolygons,
      });
    }
  });

  viz_state.dendro.active_polygon = normalizedFocus;

  if (viz_state.obs_store?.focused_dendro) {
    const focusValue = normalizedFocus ? { ...normalizedFocus } : null;
    viz_state.obs_store.focused_dendro.set(focusValue);
  }

  if (didUpdate && typeof deck_mat?.setProps === 'function') {
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
  const previousFocus = getCurrentFocus(viz_state);

  if (
    previousFocus &&
    previousFocus.axis === axis &&
    previousFocus.name === polygonName
  ) {
    applyDendroFocus(deck_mat, layers_mat, viz_state, null);
    return;
  }

  applyDendroFocus(deck_mat, layers_mat, viz_state, {
    axis,
    name: polygonName,
  });
};

const dendro_layer_onclick = (event, deck_mat, layers_mat, viz_state, axis) => {
  ensureClickTracking(viz_state);

  viz_state.dendro.clicks[axis] += 1;

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

  if (typeof viz_state.custom_callbacks[`${axis}_dendro`] === 'function') {
    viz_state.custom_callbacks[`${axis}_dendro`](
      event.object.properties.all_names
    );
  }

  if (viz_state.dendro.clicks[axis] === 1) {
    viz_state.dendro.clickTimeouts[axis] = setTimeout(() => {
      viz_state.dendro.clicks[axis] = 0;
      viz_state.dendro.clickTimeouts[axis] = null;
    }, DOUBLE_CLICK_DELAY);
  } else if (viz_state.dendro.clicks[axis] === 2) {
    if (viz_state.dendro.clickTimeouts[axis]) {
      clearTimeout(viz_state.dendro.clickTimeouts[axis]);
      viz_state.dendro.clickTimeouts[axis] = null;
    }

    viz_state.dendro.clicks[axis] = 0;

    animate_focus_to_cluster(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      event.object.properties
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
