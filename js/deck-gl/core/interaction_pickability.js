import { is_point_cloud_technology } from '../../global_variables/image_info';
import { get_layers_list } from '../utils/layers_ist';

const PICKING_RESTORE_DELAY_MS = 250;
const PICKABLE_LAYER_KEYS = ['cell_layer', 'path_layer', 'trx_layer'];

const getLayerPickable = (layer) => Boolean(layer?.props?.pickable);

const cloneLayerPickable = (layer, pickable) => {
  if (!layer || typeof layer.clone !== 'function') {
    return layer;
  }

  return layer.clone({ pickable });
};

const restorePickability = (deck_ist, layers_obj, viz_state) => {
  const state = viz_state.interaction_pickability;
  if (!state?.paused) {
    return;
  }

  if (viz_state.edit?.mode === 'sktch') {
    state.paused = false;
    state.previous = {};
    state.restoreTimer = null;
    return;
  }

  PICKABLE_LAYER_KEYS.forEach((key) => {
    if (key in state.previous) {
      layers_obj[key] = cloneLayerPickable(
        layers_obj[key],
        state.previous[key]
      );
    }
  });

  state.paused = false;
  state.previous = {};
  state.restoreTimer = null;
  deck_ist.setProps({
    layers: get_layers_list(layers_obj, viz_state.close_up),
  });
};

export const pause_point_cloud_pickability = (
  deck_ist,
  layers_obj,
  viz_state
) => {
  const technology = viz_state.img?.landscape_parameters?.technology;
  if (!is_point_cloud_technology(technology)) {
    return;
  }

  if (!viz_state.interaction_pickability) {
    viz_state.interaction_pickability = {
      paused: false,
      previous: {},
      restoreTimer: null,
    };
  }

  const state = viz_state.interaction_pickability;
  if (state.restoreTimer) {
    clearTimeout(state.restoreTimer);
  }

  if (!state.paused) {
    state.paused = true;
    state.previous = {};

    PICKABLE_LAYER_KEYS.forEach((key) => {
      const layer = layers_obj[key];
      if (!layer) {
        return;
      }

      const wasPickable = getLayerPickable(layer);
      state.previous[key] = wasPickable;

      if (wasPickable) {
        layers_obj[key] = cloneLayerPickable(layer, false);
      }
    });

    deck_ist.setProps({
      layers: get_layers_list(layers_obj, viz_state.close_up),
    });
  }

  state.restoreTimer = setTimeout(() => {
    restorePickability(deck_ist, layers_obj, viz_state);
  }, PICKING_RESTORE_DELAY_MS);
};
