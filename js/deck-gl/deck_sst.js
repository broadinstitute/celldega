import { Deck } from 'deck.gl';
import { views } from './views.js';
// import { initial_view_state } from "./initial_view_state.js";
import { layers_sst } from './layers_sst.js';
import { make_tile_tooltip } from './make_tile_tooltip.js';

export let deck_sst

export const set_deck = ( root ) => {

    let initial_view_state = {}

    deck_sst = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        layers: layers_sst,
        views: views,
        getTooltip: make_tile_tooltip,
       })

}