import { Deck } from 'deck.gl'
import { initial_view_state } from './initial_view_state.js'
import { views } from './views.js'
import { layers_ist } from './layers_ist.js'
import { on_view_state_change } from './on_view_state_change.js'
import { make_tooltip } from './make_tooltip.js'

// export let deck_ist

const getCursor = ({ isDragging }) => {
    if (isDragging) {
        return 'grabbing';
    }
    return 'pointer';
}

export const set_deck = ( root ) => {

    let deck_ist = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        views: views,
        layers: layers_ist,
        getCursor: getCursor,
        getTooltip: make_tooltip,
    })

    deck_ist.setProps({
        onViewStateChange: (params) => {
            on_view_state_change(params, deck_ist);
        }
    })

    return deck_ist

}