import { Deck } from 'deck.gl'
import { initial_view_state } from './initial_view_state.js'
import { views } from './views.js'
import { on_view_state_change } from './on_view_state_change.js'
import { make_tooltip } from './make_tooltip.js'

const getCursor = ({ isDragging }) => {
    if (isDragging) {
        return 'grabbing';
    }
    return 'pointer';
}

export const ini_deck = ( root ) => {

    let deck_ist = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        views: views,
        getCursor: getCursor,
        getTooltip: make_tooltip,
    })

    return deck_ist

}

export const set_deck_on_view_state_change = ( deck_ist, layers_obj, viz_state ) => {

    deck_ist.setProps({
        onViewStateChange: (params) => {
            on_view_state_change(params, deck_ist, layers_obj, viz_state)
        }
    })

}