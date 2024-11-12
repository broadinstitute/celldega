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
        getCursor: getCursor,
    })

    return deck_ist

}