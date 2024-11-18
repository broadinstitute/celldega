
export const redefine_global_view_state = (viz_state, viewId, zoom_curated, pan_curated) => {

    var globalViewState


    if (viewId === 'matrix') {

        globalViewState = {
            matrix: {
                zoom: [
                    zoom_curated[0],
                    zoom_curated[1]
                ],
                target: [
                    pan_curated[0],
                    pan_curated[1]
                ]
            },
            rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated[1]
                ],
                target: [
                    viz_state.viz.label_row_x,
                    pan_curated[1]
                ]
            },
            cols:   {
                zoom: [
                    zoom_curated[0],
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated[0],
                    viz_state.viz.label_col_y
                ]
            },
            dendro_rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated[1]
                ],
                target: [
                    viz_state.viz.label_row_x,
                    pan_curated[1]
                ]
            },
            dendro_cols:   {
                zoom: [
                    zoom_curated[0],
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated[0],
                    viz_state.viz.label_col_y
                ]
            }
        }

    } else if (viewId === 'cols' || viewId === 'dendro_cols'){

        globalViewState = {
            matrix: {
                zoom: [
                    zoom_curated[0],
                    zoom_curated[1]
                ],
                target: [
                    pan_curated[0],
                    viz_state.zoom.min_pan_y
                ]
            },
            rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated[1]
                ],
                target: [
                    viz_state.viz.label_row_x,
                    viz_state.zoom.min_pan_y
                ]
            },
            cols:   {
                zoom: [
                    zoom_curated[0],
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated[0],
                    viz_state.viz.label_col_y
                ]
            },
            dendro_rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated[1]
                ],
                target: [
                    viz_state.viz.label_row_x,
                    viz_state.zoom.min_pan_y
                ]
            },
            dendro_cols:   {
                zoom: [
                    zoom_curated[0],
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated[0],
                    viz_state.viz.label_col_y
                ]
            },
        }

    } else if (viewId === 'rows' || viewId === 'dendro_rows'){

        globalViewState = {
            matrix: {
                zoom: [
                    zoom_curated[0],
                    zoom_curated[1]
                ],
                target: [
                    viz_state.zoom.min_pan_x,
                    pan_curated[1]
                ]
            },
            rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated[1]
                ],
                target:[
                    viz_state.viz.label_row_x,
                    pan_curated[1]
                ]
            },
            cols:   {
                zoom: [
                    zoom_curated[0],
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated[0],
                    viz_state.viz.label_col_y
                ]
            },
            dendro_rows:   {
                zoom: [
                    viz_state.zoom.ini_zoom_x,
                    zoom_curated[1]
                ],
                target:[
                    viz_state.viz.label_row_x,
                    pan_curated[1]
                ]
            },
            dendro_cols:   {
                zoom: [
                    zoom_curated[0],
                    viz_state.zoom.ini_zoom_y
                ],
                target: [
                    pan_curated[0],
                    viz_state.viz.label_col_y
                ]
            },
        }

    }

    return globalViewState
}
