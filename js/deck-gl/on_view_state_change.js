import { debounce } from "../utils/debounce.js";
import { calc_viewport } from './calc_viewport.js';
import { bounce_time } from '../global_variables/bounce_time.js';

export const on_view_state_change = debounce(({ viewState }) => {
    calc_viewport(viewState);
    return viewState;
}, bounce_time);