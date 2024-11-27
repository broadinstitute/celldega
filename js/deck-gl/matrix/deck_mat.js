import { Deck } from 'deck.gl'

const getCursor = ({ isDragging }) => {
    if (isDragging) {
        return 'grabbing';
    }
    return 'pointer';
}

export const ini_deck = ( root, width, height ) => {

    // if width is a number then it is implied to be in pixels
    // and needs to have a buffer added to it
    if (typeof width === 'number'){
        width = width + 100
        height = height + 100
    }

    let deck_ist = new Deck({
        parent: root,
        getCursor: getCursor,
        width: width,
        height: height,
    })

    return deck_ist

}