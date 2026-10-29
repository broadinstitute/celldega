import { debounce } from '../../utils/debounce';

import { calc_viewport } from './calc_viewport';

const bounce_time = 200;

export const on_view_state_change = debounce(
  ({ viewState }, deck_ist, layers_obj, viz_state) => {
    if (viz_state.obs_store.umap_state.get() === false) {
      calc_viewport(viewState, deck_ist, layers_obj, viz_state);
    }

    if (viz_state.scale_bar) {
      viz_state.obs_store.scale_bar_view_state.set(viewState);
    }

    if (typeof viz_state.custom_callbacks.view_change === 'function') {
      viz_state.custom_callbacks.view_change(
        viewState,
        viz_state.close_up,
        layers_obj.trx_layer
      );
    }

    return viewState;
  },
  bounce_time
);
