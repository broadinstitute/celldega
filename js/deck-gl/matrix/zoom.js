export const update_zoom_data = (zoom_data, viewId, zoom, target) => {

    if (viewId === 'matrix') {

        // update pans
        zoom_data.pan_x = target[0];
        zoom_data.pan_y = target[1];

        // update zooms
        zoom_data.zoom_x = zoom[0]
        zoom_data.zoom_y = zoom[1]

    } else if (viewId === 'cols') {

        console.log('cols')

        // update pan_x
        zoom_data.pan_x = target[0]

        // update zooms
        zoom_data.zoom_x = zoom[0]

        // // switch to y zoom
        // ////////////////////////
        // // update pan_x
        // zoom_data.pan_x = target[0]

        // // update zooms
        // zoom_data.zoom_y = zoom[1]

    } else if (viewId === 'rows') {

        console.log('rows')

        // update pan_y
        zoom_data.pan_y = target[1];

        // update zooms
        zoom_data.zoom_y = zoom[1]

    }
}