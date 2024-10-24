import { Deck } from 'deck.gl';

export const ini_deck_sst = ( root ) => {

    let deck_sst = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},

    })

    return deck_sst

}