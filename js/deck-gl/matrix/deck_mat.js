import { Deck } from 'deck.gl'

const getCursor = ({ isDragging }) => {
    if (isDragging) {
        return 'grabbing';
    }
    return 'pointer';
}

export const ini_deck = ( root ) => {

    let deck_ist = new Deck({
        parent: root,
        // controller: {
        //     doubleClickZoom: false,
        //     scrollZoom: true,
        //     inertia: true,
        //     zoomAxis: 'Y'
        // },
        getCursor: getCursor,
    })

    return deck_ist

}