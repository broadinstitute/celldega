export const update_zoom_data = (viz_state, viewId, zoom_curated, pan_curated) => {

    let zoom_data = viz_state.zoom.zoom_data

    zoom_data.matrix.pan_x = pan_curated[0];
    zoom_data.matrix.pan_y = pan_curated[1];
    zoom_data.matrix.zoom_x = zoom_curated[0]
    zoom_data.matrix.zoom_y = zoom_curated[1]

    zoom_data.rows.pan_x = viz_state.zoom.ini_pan_x
    zoom_data.rows.pan_y = pan_curated[1]
    zoom_data.rows.zoom_x = zoom_curated[0]
    zoom_data.rows.zoom_y = zoom_curated[1]

    zoom_data.cols.pan_x = pan_curated[0]
    zoom_data.cols.pan_y = viz_state.zoom.ini_pan_y
    zoom_data.cols.zoom_x = zoom_curated[0]
    zoom_data.cols.zoom_y = zoom_curated[1]

    zoom_data.dendro_rows.pan_x = viz_state.zoom.ini_pan_x
    zoom_data.dendro_rows.pan_y = pan_curated[1]
    zoom_data.dendro_rows.zoom_x = zoom_curated[0]
    zoom_data.dendro_rows.zoom_y = zoom_curated[1]

    zoom_data.dendro_cols.pan_x = pan_curated[0]
    zoom_data.dendro_cols.pan_y = viz_state.zoom.ini_pan_y
    zoom_data.dendro_cols.zoom_x = zoom_curated[0]
    zoom_data.dendro_cols.zoom_y = zoom_curated[1]

}

export const ini_zoom_data = (viz_state) => {
    viz_state.zoom.zoom_data = {}

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

    viz_state.zoom.zoom_data.dendro_rows = {
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    }

    viz_state.zoom.zoom_data.dendro_cols = {
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    }

}