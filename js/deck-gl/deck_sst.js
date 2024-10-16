import { Deck } from 'deck.gl';
import { layers_sst } from './layers_sst.js';
import { make_tile_tooltip } from './make_tile_tooltip.js';
import { OrthographicView } from 'deck.gl';

export const ini_deck_sst = ( root ) => {

    console.log('ini_deck_sst')

    const views = [ new OrthographicView({id: 'ortho'})]

    const ini_x = 1000
    const ini_y = 5000
    const ini_z = 0
    const ini_zoom = -3

    const initial_view_state = {
        target: [ini_x, ini_y, ini_z],
        zoom: ini_zoom
    }

    let deck_sst = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        layers: layers_sst,
        views: views,
        getTooltip: make_tile_tooltip,
    })

    return deck_sst

}