import { debounce } from "../utils/debounce.js";
import { calc_viewport } from './calc_viewport.js';

const bounce_time = 200

export const on_view_state_change = debounce(({ viewState }) => {
    
    calc_viewport(viewState);
    return viewState;
}, bounce_time);