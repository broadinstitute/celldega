import { Deck } from 'deck.gl';
import { views } from '../deck-gl/views.js';
import { initial_view_state } from "../deck-gl/initial_view_state.js";
import { layers } from '../deck-gl/toy_layers.js';

export let deck

export const set_deck = ( root ) => {

    deck = new Deck({
        parent: root,
        controller: true,
        initialViewState: initial_view_state,
        layers: layers,    
        views: views
       })

}