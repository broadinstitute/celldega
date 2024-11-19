import { PolygonLayer } from 'deck.gl'

export const ini_dendro_layer = (layers_mat, viz_state, axis) => {

    const inst_layer = new PolygonLayer({
        id: axis + '-dendro-layer',
        data: viz_state.dendro.polygons[axis],
        getPolygon: (d) => d.coordinates,
        getFillColor: [0, 0, 0, 90],
        getLineColor: [255, 255, 255, 255],
        lineWidthMinPixels: 0,
        pickable: true,
        // autoHighlight: true, // Highlight on hover
        // onHover: ({ object }) => console.log(object?.properties.name), // Hover info
    })

    return inst_layer

}