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
        antialiasing: false,
        // autoHighlight: true, // Highlight on hover
        // onHover: ({ object }) => console.log(object?.properties.name), // Hover info
    })

    return inst_layer

}

export const update_dendro_layer_data = (layers_mat, viz_state, axis) => {

    layers_mat[axis + '_dendro_layer'] = layers_mat[axis + '_dendro_layer'].clone({
        data: viz_state.dendro.polygons[axis],
    })

}

export const toggle_dendro_layer_visibility = (layers_mat, viz_state, axis) => {

    // if viz_state.order.curent[axis] is 'clust' then the dendrogram is visible
    let is_visible = false
    if (viz_state.order.current[axis] === 'clust'){
        is_visible = true
    }

    layers_mat[axis + '_dendro_layer'] = layers_mat[axis + '_dendro_layer'].clone({
        // visible: !layers_mat[axis + '_dendro_layer'].visible,
        visible: is_visible,
    })

    // // set the status of the dendrogram slider
    // viz_state.dendro.sliders[axis].visible = is_visible

}