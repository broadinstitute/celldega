import { debounce } from "../utils/debounce.js";
import { calc_viewport } from './calc_viewport.js';

const bounce_time = 200

export const on_view_state_change = debounce(({ viewState }, deck_ist, layers_obj, viz_state) => {

    console.log('ist on_view_state_change')

    calc_viewport(viewState, deck_ist, layers_obj, viz_state)

    console.log(viz_state.custom_callbacks)

    if (typeof viz_state.custom_callbacks.view_change === 'function') {
        viz_state.custom_callbacks.view_change(
            viewState,
            viz_state.close_up,
            layers_obj.trx_layer
        )
    }

    return viewState

}, bounce_time);