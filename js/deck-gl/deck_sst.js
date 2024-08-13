import { Deck } from 'deck.gl';
import { layers_sst } from './layers_sst.js';
import { make_tile_tooltip } from './make_tile_tooltip.js';
import { OrthographicView } from 'deck.gl';

export let deck_sst

export const set_deck = ( root ) => {

    views = [ new OrthographicView({id: 'ortho'})]

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