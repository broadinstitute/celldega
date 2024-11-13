import { OrthographicView } from 'deck.gl'
import { update_zoom_data } from './zoom.js'
import { get_layers_list } from './matrix_layers.js'
import { redefine_global_view_state } from './views.js'

export const on_view_state_change = (params, deck_mat, layers_mat, viz_state) => {

    const viewState = params.viewState
    const viewId = params.viewId

    const {zoom, target} = viewState;

    var global_view_state = redefine_global_view_state(viz_state, viewId, zoom, target)

    let zoom_factor
    if (viz_state.zoom.zoom_axis === 'X'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.mat.zoom_x)
    } else if (viz_state.zoom.zoom_axis === 'Y'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.mat.zoom_y)
    } else if (viz_state.zoom.zoom_axis === 'all'){
        zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.mat.zoom_x)
    }

    viz_state.viz.inst_font_size = viz_state.viz.ini_font_size * zoom_factor

    update_zoom_data(viz_state, viewId, zoom, target)

    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        getSize: viz_state.viz.inst_font_size,
    })

    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        getSize: viz_state.viz.inst_font_size,
    })


    let zoom_mode
    if (viz_state.zoom.zoom_axis !== 'all'){
        zoom_mode = zoom_factor < viz_state.zoom.switch_ratio ? viz_state.zoom.zoom_axis : 'all'
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