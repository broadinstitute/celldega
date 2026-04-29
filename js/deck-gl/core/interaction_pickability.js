import { is_point_cloud_technology } from '../../global_variables/image_info';

const PICKING_RESTORE_DELAY_MS = 250;

const restorePickability = (deck_ist, viz_state) => {
  const state = viz_state.interaction_pickability;
  if (!state?.paused) {
    return;
  }

  if (viz_state.edit?.mode === 'sktch') {
    state.paused = false;
    state.previousDeckPickable = true;
    state.restoreTimer = null;
    return;
  }

  deck_ist.setProps({
    _pickable: state.previousDeckPickable,
  });

  state.paused = false;
  state.previousDeckPickable = true;
  state.restoreTimer = null;
};

export const pause_point_cloud_pickability = (
  deck_ist,
  _layers_obj,
  viz_state
) => {
  const technology = viz_state.img?.landscape_parameters?.technology;
  if (!is_point_cloud_technology(technology)) {
    return;
  }

  if (!viz_state.interaction_pickability) {
    viz_state.interaction_pickability = {
      paused: false,
      previousDeckPickable: true,
      restoreTimer: null,
    };
  }

  const state = viz_state.interaction_pickability;
  if (state.restoreTimer) {
    clearTimeout(state.restoreTimer);
  }

  if (!state.paused) {
    state.paused = true;
    state.previousDeckPickable = deck_ist.props?._pickable !== false;

    deck_ist.setProps({
      _pickable: false,
    });
  }

  state.restoreTimer = setTimeout(() => {
    restorePickability(deck_ist, viz_state);
  }, PICKING_RESTORE_DELAY_MS);
};
