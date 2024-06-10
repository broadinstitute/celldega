import { Deck } from 'deck.gl';
import { views } from './views.js';
import { initial_view_state } from "./initial_view_state.js";
import { layers } from './layers_sst.js';
import { make_tile_tooltip } from './make_tile_tooltip.js';

export let deck

export const set_deck = ( root ) => {

    deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        layers: layers,    
        views: views,
        getTooltip: make_tile_tooltip,
       })

}