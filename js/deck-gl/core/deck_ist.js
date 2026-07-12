import { Deck, OrbitController } from 'deck.gl';

import { make_tooltip } from '../utils/tooltips';

import { on_view_state_change } from './on_view_state_change';

const getCursor = ({ isDragging }) => {
  if (isDragging) {
    return 'grabbing';
  }
  return 'pointer';
};

export const ini_deck = (root, width, height, technology = '') => {
  const controller = { doubleClickZoom: false };
  if (technology === 'point-cloud') {
    controller.type = OrbitController;
  }

  const deck_ist = new Deck({
    parent: root,
    controller,
    getCursor,
    width,
    height,
    // preserveDrawingBuffer lets us read the canvas back as a PNG (raster capture)
    // at any time via canvas.toDataURL(); see landscape captureRaster().
    deviceProps: { type: 'webgl', preserveDrawingBuffer: true },
  });

  return deck_ist;
};

export const set_views_prop = (deck_ist, views) => {
  deck_ist.setProps({
    views,
  });
};

export const set_get_tooltip = (deck_ist, viz_state) => {
  deck_ist.setProps({
    getTooltip: (info) => make_tooltip(viz_state, info),
  });
};

export const set_deck_on_view_state_change = (
  deck_ist,
  layers_obj,
  viz_state
) => {
  deck_ist.setProps({
    onViewStateChange: (params) => {
      // Track the latest view state (synchronously, before the debounced handler) so
      // raster capture can record the exact zoom/pan for reproducibility.
      viz_state.current_view_state = params.viewState;
      on_view_state_change(params, deck_ist, layers_obj, viz_state);
    },
  });
};

export const set_initial_view_state = (
  deck_ist,
  ini_x,
  ini_y,
  ini_z,
  ini_zoom,
  viz_state,
  rotation_orbit = 0,
  rotation_x = 0
) => {
  const {
    center_x,
    center_y,
    center_z = 0,
    ini_zoom: initial_zoom,
  } = viz_state.spatial;

  if (ini_x === 0 && ini_y === 0 && ini_z === 0 && ini_zoom === 0) {
    ini_x = center_x;
    ini_y = center_y;
    ini_z = center_z;
    ini_zoom = initial_zoom;
  }

  const initial_view_state = {
    target: [ini_x, ini_y, ini_z],
    zoom: ini_zoom,
  };

  if (viz_state.img.landscape_parameters.technology === 'point-cloud') {
    initial_view_state.rotationOrbit = rotation_orbit;
    initial_view_state.rotationX = rotation_x;
  }

  deck_ist.setProps({
    initialViewState: initial_view_state,
  });

  // Seed the tracked view state so a capture before any pan/zoom still records it.
  viz_state.current_view_state = initial_view_state;

  if (viz_state.scale_bar) {
    viz_state.obs_store.scale_bar_view_state.set(initial_view_state);
  }
};
