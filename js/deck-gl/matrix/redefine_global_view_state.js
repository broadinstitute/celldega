import { curate_pan_x, curate_pan_y } from './curate_pan.js'

export const redefine_global_view_state = (viz_state, viewId, zoom, target) => {

    const zoom_data = viz_state.zoom.zoom_data

    console.log('zoom', zoom[0].toFixed(2), zoom[1].toFixed(2))

    console.log('    ')


    var globalViewState

    var min_zoom_x = 0
    var min_zoom_y = 0

    var zoom_curated_x = Math.max(min_zoom_x, zoom[0])
    var zoom_curated_y = Math.max(min_zoom_y, zoom[1])

    if (viz_state.zoom.zoom_axis === 'X'){
        zoom_curated_y = zoom_curated_x - viz_state.zoom.zoom_delay
    } else if (viz_state.zoom.zoom_axis === 'Y'){
        zoom_curated_x = zoom_curated_y - viz_state.zoom.zoom_delay
    }

    zoom_curated_x = Math.max(min_zoom_x, zoom_curated_x)
    zoom_curated_y = Math.max(min_zoom_y, zoom_curated_y)

    if (viewId === 'rows'){
        // use the other axis to keep track of the raw zoom
        viz_state.zoom.zoom_data.raw_zoom = zoom_curated_y
    } else if (viewId === 'cols'){

        console.log(zoom)
        viz_state.zoom.zoom_data.raw_zoom = zoom_curated_x

        console.log('cols raw zoom', viz_state.zoom.zoom_data.raw_zoom)

    } else if (viewId === 'matrix') {
        if (viz_state.zoom.zoom_axis === 'X'){
            viz_state.zoom.zoom_data.raw_zoom = zoom_curated_x
        } else if (viz_state.zoom.zoom_axis === 'Y'){
            viz_state.zoom.zoom_data.raw_zoom = zoom_curated_y
        } else if (viz_state.zoom.zoom_axis === 'all'){
            viz_state.zoom.zoom_data.raw_zoom = zoom_curated_x
        }
    }

    console.log('matrix', {
        pan_x:  zoom_data.mat.pan_x.toFixed(2),
        pan_y:  zoom_data.mat.pan_y.toFixed(2),
        zoom_x: zoom_data.mat.zoom_x.toFixed(2),
        zoom_y: zoom_data.mat.zoom_y.toFixed(2),
    })

    console.log('raw_zoom', viz_state.zoom.zoom_data.raw_zoom.toFixed(2))

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
                    viz_state.zoom.zoom_data.raw_zoom
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
