import { Deck, OrbitController } from 'deck.gl';

import { is_orbit_technology } from '../../global_variables/image_info';
import { check_nbhd_cloud_camera_side } from '../layers/nbhd_cloud_shapes_layer';
import { make_tooltip } from '../utils/tooltips';

import {
  pause_point_cloud_pickability,
  setup_point_cloud_pickability_events,
} from './interaction_pickability';
import { on_view_state_change } from './on_view_state_change';

const getCursor = ({ isDragging }) => {
  if (isDragging) {
    return 'grabbing';
  }
  return 'pointer';
};

export const ini_deck = (
  root,
  width,
  height,
  technology = '',
  { per_view_controllers = false } = {}
) => {
  const deck_props = { parent: root, getCursor, width, height };

  // A multi-view deck (e.g. Landmark's two side-by-side panels) manages a
  // controller per view via the `views` prop. A top-level `controller` here
  // would additionally bind to the default view at the canvas origin — which
  // the first/left view (also at 0,0) then inherits instead of its own
  // per-view `dragPan:false`, so dragging a marker on the left panel also pans
  // the camera. Omit the top-level controller in that case.
  if (!per_view_controllers) {
    const controller = { doubleClickZoom: false };
    if (is_orbit_technology(technology)) {
      controller.type = OrbitController;
    }
    deck_props.controller = controller;
  }

  return new Deck(deck_props);
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
  setup_point_cloud_pickability_events(deck_ist, viz_state);
};

export const set_deck_on_view_state_change = (
  deck_ist,
  layers_obj,
  viz_state
) => {
  deck_ist.setProps({
    onViewStateChange: (params) => {
      pause_point_cloud_pickability(deck_ist, layers_obj, viz_state);
      // Runs on every raw frame, not behind on_view_state_change's 200ms
      // debounce -- see check_nbhd_cloud_camera_side's own comment for why
      // that's safe.
      check_nbhd_cloud_camera_side(params.viewState, layers_obj, viz_state);
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

  if (is_orbit_technology(viz_state.img.landscape_parameters.technology)) {
    initial_view_state.rotationOrbit = rotation_orbit;
    initial_view_state.rotationX = rotation_x;
  }

  deck_ist.setProps({
    initialViewState: initial_view_state,
  });

  if (viz_state.scale_bar) {
    viz_state.obs_store.scale_bar_view_state.set(initial_view_state);
  }
};
