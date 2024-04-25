import { Deck } from 'deck.gl';
import { initial_view_state } from '../deck-gl/initial_view_state.js';
import { views } from '../deck-gl/views.js';
import { layers } from '../deck-gl/layers.js';
// import { on_view_state_change } from '../deck-gl/on_view_state_change.js';
import { make_tooltip } from '../deck-gl/make_tooltip.js';

export let deck

export const set_deck = ( root, on_view_state_change ) => {

    deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        views: views,
        layers: layers,
        onViewStateChange: on_view_state_change,
        getTooltip: make_tooltip,
    }); 

}