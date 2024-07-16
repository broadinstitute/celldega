import { Deck } from 'deck.gl'
import { initial_view_state } from './initial_view_state.js'
import { views } from './views.js'
import { layers } from './layers_ist.js'
import { on_view_state_change } from './on_view_state_change.js'
import { make_tooltip } from './make_tooltip.js'

export let deck_ist

export const set_deck = ( root ) => {

    deck_ist = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        views: views,
        layers: layers,
        onViewStateChange: on_view_state_change,
        getTooltip: make_tooltip,
    });

}