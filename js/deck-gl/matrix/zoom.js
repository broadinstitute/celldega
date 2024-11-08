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

export const ini_zoom_data = (viz_state) => {
    viz_state.zoom.zoom_data = ({
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    })
}