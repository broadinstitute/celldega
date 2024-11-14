import { OrthographicView } from 'deck.gl'
import { update_zoom_data } from './zoom.js'
import { get_layers_list } from './matrix_layers.js'
import { redefine_global_view_state } from './redefine_global_view_state.js'
import { curate_pan_x, curate_pan_y } from './curate_pan.js'

export const on_view_state_change = (params, deck_mat, layers_mat, viz_state) => {

    const viewState = params.viewState
    const viewId = params.viewId

    const {zoom, target} = viewState;

    // zoom differentials are calculated before the redefine_global_view_state function

    let zoom_dx
    let zoom_dy

    if (viewId === 'cols'){

        if (viz_state.zoom.minor_zoom_axis === 'X'){

            zoom_dx = zoom[0]
            zoom_dy = zoom[1]

        } else if (viz_state.zoom.minor_zoom_axis === 'Y'){

            zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
            zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

        } else if (viz_state.zoom.minor_zoom_axis === 'none'){

            zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
            zoom_dy = zoom[1]

        }

    } else if (viewId === 'rows'){

        if (viz_state.zoom.minor_zoom_axis === 'Y'){

            zoom_dx = zoom[0]
            zoom_dy = zoom[1]

        } else if (viz_state.zoom.minor_zoom_axis === 'X'){

            zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
            zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

        } else if (viz_state.zoom.minor_zoom_axis === 'none'){

            zoom_dx = zoom[0]
            zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

        }


    }  else if (viewId === 'matrix'){

        zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
        zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

    }

    viz_state.zoom.zoom_data.total_zoom.x += zoom_dx
    viz_state.zoom.zoom_data.total_zoom.y += zoom_dy

    // keep zoom within bounds
    viz_state.zoom.zoom_data.total_zoom.x = Math.max(0, viz_state.zoom.zoom_data.total_zoom.x)
    viz_state.zoom.zoom_data.total_zoom.y = Math.max(0, viz_state.zoom.zoom_data.total_zoom.y)

    // console.log('differential zooms', zoom_dy)
    // console.log(viewId)
    // console.log('data', viz_state.zoom.zoom_data.matrix.zoom_y.toFixed(2))

    let new_zoom = [viz_state.zoom.zoom_data.total_zoom.x, viz_state.zoom.zoom_data.total_zoom.y]
    // console.log('new_zoom ', new_zoom)
    // console.log('   ')


    var zoom_curated_x = Math.max(0, new_zoom[0])
    var zoom_curated_y = Math.max(0, new_zoom[1])

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

    let zoom_curated = [zoom_curated_x, zoom_curated_y]
    let pan_curated = [pan_curated_x, pan_curated_y]

    var global_view_state = redefine_global_view_state(viz_state, viewId, zoom_curated, pan_curated)

    // update_zoom_data(viz_state, viewId, new_zoom, target)
    update_zoom_data(viz_state, viewId, zoom_curated, pan_curated)

    let zoom_factor
    if (viz_state.zoom.major_zoom_axis === 'X'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x)
    } else if (viz_state.zoom.major_zoom_axis === 'Y'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_y)
    } else if (viz_state.zoom.major_zoom_axis === 'all'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x)
    }

    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        getSize: viz_state.viz.font_size.rows * Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_y),
    })

    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        getSize: viz_state.viz.font_size.cols * Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x),
        updateTriggers: {
            getPixelOffset: viz_state.zoom.zoom_data.matrix.zoom_x
        }
    })


    let zoom_mode
    if (viz_state.zoom.major_zoom_axis !== 'all'){
        zoom_mode = zoom_factor < viz_state.zoom.switch_ratio ? viz_state.zoom.major_zoom_axis : 'all'
    } else {
        zoom_mode = 'all'
    }

    // Recreate each view with updated zoomAxis in controller
    viz_state.views.views_list = viz_state.views.views_list.map(view => {
        return new OrthographicView({
            ...view.props,
            controller: {
                ...view.props.controller,
                doubleClickZoom: false,
                scrollZoom: true,
                inertia: true,
                zoomAxis: zoom_mode,
            },
        });
    });

    deck_mat.setProps({
        viewState: global_view_state,
        layers: get_layers_list(layers_mat),
        views: viz_state.views.views_list,
    })

}