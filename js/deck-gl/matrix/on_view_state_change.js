import { OrthographicView } from 'deck.gl'
import { update_zoom_data } from './zoom.js'
import { get_layers_list } from './matrix_layers.js'
import { redefine_global_view_state } from './redefine_global_view_state.js'

export const on_view_state_change = (params, deck_mat, layers_mat, viz_state) => {

    const viewState = params.viewState
    const viewId = params.viewId

    const {zoom, target} = viewState;

    // zoom differentials are calculated before the redefine_global_view_state function

    let zoom_dx
    let zoom_dy

    if (viewId === 'cols'){

        if (viz_state.zoom.minor_zoom_axis === 'X'){

            console.log('stateless zooming')
            zoom_dx = zoom[0]
            zoom_dy = zoom[1]

        } else {

            zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
            zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

        }

    } else if (viewId === 'rows'){

        if (viz_state.zoom.minor_zoom_axis === 'Y'){

            console.log('stateless zooming')
            zoom_dx = zoom[0]
            zoom_dy = zoom[1]

        } else {

            zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
            zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

        }
    }  else if (viewId === 'matrix'){

        zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x
        zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y

    }

    viz_state.zoom.zoom_data.total_zoom.x += zoom_dx
    viz_state.zoom.zoom_data.total_zoom.y += zoom_dy

    // console.log('compare zooms')

    console.log('differential zooms', zoom_dy)

    console.log(viewId)
    console.log('data', viz_state.zoom.zoom_data.matrix.zoom_y.toFixed(2))

    let new_zoom = [viz_state.zoom.zoom_data.total_zoom.x, viz_state.zoom.zoom_data.total_zoom.y]
    console.log('new_zoom ', new_zoom)
    console.log('   ')

    var global_view_state = redefine_global_view_state(viz_state, viewId, new_zoom, target)

    let zoom_factor
    if (viz_state.zoom.major_zoom_axis === 'X'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x)
    } else if (viz_state.zoom.major_zoom_axis === 'Y'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_y)
    } else if (viz_state.zoom.major_zoom_axis === 'all'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x)
    }

    viz_state.viz.inst_font_size = viz_state.viz.ini_font_size * zoom_factor

    // update_zoom_data(viz_state, viewId, zoom, target)
    update_zoom_data(viz_state, viewId, new_zoom, target)

    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        getSize: viz_state.viz.inst_font_size,
    })

    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        getSize: viz_state.viz.inst_font_size,
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