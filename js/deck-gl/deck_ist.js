import { Deck } from 'deck.gl'
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
        views: views,
        getCursor: getCursor,
        // getTooltip: (info) => make_tooltip(info),
    })

    return deck_ist

}

export const set_get_tooltip = (deck_ist, viz_state) => {

        deck_ist.setProps({
            getTooltip: (info) => make_tooltip(viz_state, info)
        })

    }

export const set_deck_on_view_state_change = (deck_ist, layers_obj, viz_state) => {

    deck_ist.setProps({
        onViewStateChange: (params) => {
            on_view_state_change(params, deck_ist, layers_obj, viz_state)
        }
    })

}


export const set_initial_view_state = (deck_ist, ini_x, ini_y, ini_z, ini_zoom) => {

    const initial_view_state = {
        target: [ini_x, ini_y, ini_z],
        zoom: ini_zoom
    }

    deck_ist.setProps({
        initialViewState: initial_view_state
    })
}