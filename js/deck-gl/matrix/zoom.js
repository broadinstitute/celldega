export const update_zoom_data = (viz_state, viewId, zoom, target) => {

    let zoom_data = viz_state.zoom.zoom_data

    zoom_data.matrix.pan_x = target[0];
    zoom_data.matrix.pan_y = target[1];
    zoom_data.matrix.zoom_x = zoom[0]
    zoom_data.matrix.zoom_y = zoom[1]

    zoom_data.rows.pan_x = viz_state.zoom.ini_pan_x
    zoom_data.rows.pan_y = target[1]
    zoom_data.rows.zoom_x = zoom[0]
    zoom_data.rows.zoom_y = zoom[1]

    zoom_data.cols.pan_x = target[0]
    zoom_data.cols.pan_y = viz_state.zoom.ini_pan_y
    zoom_data.cols.zoom_x = zoom[0]
    zoom_data.cols.zoom_y = zoom[1]

}

export const ini_zoom_data = (viz_state) => {
    viz_state.zoom.zoom_data = {}

    viz_state.zoom.zoom_data.raw_zoom = viz_state.zoom.ini_zoom_x

    viz_state.zoom.zoom_data.total_zoom = {}
    viz_state.zoom.zoom_data.total_zoom.x = 0
    viz_state.zoom.zoom_data.total_zoom.y = 0

    viz_state.zoom.zoom_data.matrix = {
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    }

    viz_state.zoom.zoom_data.rows = {
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    }

    viz_state.zoom.zoom_data.cols = {
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    }

}