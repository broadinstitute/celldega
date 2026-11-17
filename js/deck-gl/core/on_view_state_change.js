import { debounce } from '../../utils/debounce';
import { announce_view } from '../../viz/view_requests';

import { calc_viewport } from './calc_viewport';

// A view change this soon after opening a Snapshot or pin is that move settling,
// not the scientist moving the view.
const OWN_MOVE_MS = 1000;

const bounce_time = 200;

const make_view_handler = () =>
  debounce(({ viewState }, deck_ist, layers_obj, viz_state) => {
    calc_viewport(viewState, deck_ist, layers_obj, viz_state);

    if (viz_state.scale_bar) {
      viz_state.obs_store.scale_bar_view_state.set(viewState);
    }

    // The scientist moved the view: no Snapshot is shown exactly any more, so the
    // linked Snapshot cards drop their "shown" mark.
    const shown = viz_state.model?.get?.('view_result')?.shown;
    if (
      shown &&
      Date.now() - (viz_state.programmatic_view_at || 0) > OWN_MOVE_MS
    ) {
      announce_view(viz_state.model, '');
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
