import { curate_pan_x, curate_pan_y } from './curate_pan.js'

export const redefine_global_view_state = (viz_state, viewId, zoom, target) => {

    var globalViewState

    var zoom_curated_x = Math.max(0, zoom[0])
    var zoom_curated_y = Math.max(0, zoom[1])

    // delay zoom based on row/col ratio
    if (viz_state.zoom.major_zoom_axis === 'X'){
        zoom_curated_y = zoom_curated_x - viz_state.zoom.zoom_delay
    } else if (viz_state.zoom.major_zoom_axis === 'Y'){
        zoom_curated_x = zoom_curated_y - viz_state.zoom.zoom_delay
    }

    // keep zoom within bounds
    zoom_curated_x = Math.max(0, zoom_curated_x)
    zoom_curated_y = Math.max(0, zoom_curated_y)

    var pan_curated_x = curate_pan_x(target[0], zoom_curated_x, viz_state)
    var pan_curated_y = curate_pan_y(target[1], zoom_curated_y, viz_state)


    if (viewId === 'matrix') {

        globalViewState = {
            matrix: {
                zoom: [
                    zoom_curated_x,
                    zoom_curated_y
                ],
                target: [
                    pan_curated_x,
                    pan_curated_y
                ]
            },
            rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated_y
                ],
                target: [
                    viz_state.viz.label_row_x,
                    pan_curated_y
                ]
            },
            cols:   {
                zoom: [
                    zoom_curated_x,
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated_x,
                    viz_state.viz.label_col_y
                ]
            },
        }

    } else if (viewId === 'cols'){

        globalViewState = {
            matrix: {
                zoom: [
                    zoom_curated_x,
                    zoom_curated_y
                ],
                target: [
                    pan_curated_x,
                    viz_state.zoom.min_pan_y
                ]
            },
            rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated_y
                ],
                target: [
                    viz_state.viz.label_row_x,
                    viz_state.zoom.min_pan_y
                ]
            },
            cols:   {
                zoom: [
                    zoom_curated_x,
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated_x,
                    viz_state.viz.label_col_y
                ]
            },
        }

    } else if (viewId === 'rows'){

        globalViewState = {
            matrix: {
                zoom: [
                    zoom_curated_x,
                    zoom_curated_y
                ],
                target: [
                    viz_state.zoom.min_pan_x,
                    pan_curated_y
                ]
            },
            rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated_y
                ],
                target:[
                    viz_state.viz.label_row_x,
                    pan_curated_y
                ]
            },
            cols:   {
                zoom: [
                    zoom_curated_x,
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated_x,
                    viz_state.viz.label_col_y
                ]
            },
        }

    }

    return globalViewState
}
