import { PathLayer } from 'deck.gl';

export const make_polygon_layer = () => {

    console.log('making polygon layer in a function')
    return new PathLayer({
        id: 'path_layer',
        data: [],
        pickable: true,
        widthScale: 3,
        widthMinPixels: 1,
        getPath: d => d,
        getColor: [255, 255, 255, 150], // white outline
        widthUnits: 'pixels',
    })
}