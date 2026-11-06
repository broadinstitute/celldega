import { debounce } from '../../utils/debounce';

import { calc_viewport } from './calc_viewport';

const bounce_time = 200;

const make_view_handler = () =>
  debounce(({ viewState }, deck_ist, layers_obj, viz_state) => {
    calc_viewport(viewState, deck_ist, layers_obj, viz_state);

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
  }, bounce_time);

// Each Landscape must finish its own viewport update when widgets share a page.
const view_handlers = new WeakMap();
export const on_view_state_change = (
  event,
  deck_ist,
  layers_obj,
  viz_state
) => {
  if (!view_handlers.has(viz_state))
    view_handlers.set(viz_state, make_view_handler());
  return view_handlers.get(viz_state)(event, deck_ist, layers_obj, viz_state);
};
