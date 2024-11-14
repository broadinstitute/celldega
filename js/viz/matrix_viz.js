import { ini_deck } from '../deck-gl/matrix/deck_mat.js'
import { set_mat_data } from '../matrix/mat_data.js';
import { set_mat_constants } from '../matrix/set_constants.js';
import { set_row_label_data, set_col_label_data } from '../matrix/label_data.js';
import { set_row_cat_data, set_col_cat_data } from '../matrix/cat_data.js';
import { ini_mat_layer, set_mat_layer_onclick } from '../deck-gl/matrix/mat_layer.js';
import { ini_row_label_layer, ini_col_label_layer } from '../deck-gl/matrix/label_layers.js';
import { ini_row_cat_layer, ini_col_cat_layer } from '../deck-gl/matrix/cat_layers.js';
import { get_layers_list, layer_filter } from '../deck-gl/matrix/matrix_layers.js'
import { ini_views, ini_view_state } from '../deck-gl/matrix/views.js'
import { on_view_state_change } from '../deck-gl/matrix/on_view_state_change.js'
import { ini_zoom_data } from '../deck-gl/matrix/zoom.js'
import { get_tooltip } from '../deck-gl/matrix/matrix_tooltip.js'

export const matrix_viz = async (
    model,
    el,
    network,
    width,
    height
    // token,
) => {

    console.log('here??????????????')

    const root = document.createElement("div")
    let deck_mat = ini_deck(root)

    let viz_state = set_mat_constants(network, root, width, height)
    set_mat_data(network, viz_state)

    console.log('here')

    viz_state.labels = {}

    console.log('ini_zoom_data')
    ini_zoom_data(viz_state)

    viz_state.labels.row_label_data = set_row_label_data(network, viz_state)
    viz_state.labels.col_label_data = set_col_label_data(network, viz_state)

    viz_state.cats.row_cat_data = set_row_cat_data(network, viz_state)
    viz_state.cats.col_cat_data = set_col_cat_data(network, viz_state)

    let layers_mat = {}
    layers_mat.mat_layer = ini_mat_layer(viz_state)
    layers_mat.row_label_layer = ini_row_label_layer(viz_state)
    layers_mat.col_label_layer = ini_col_label_layer(viz_state)
    layers_mat.row_cat_layer = ini_row_cat_layer(viz_state)
    layers_mat.col_cat_layer = ini_col_cat_layer(viz_state)

    ini_views(viz_state)


    const global_view_state = ini_view_state(viz_state)

    console.log(viz_state)

    console.log('layers_mat', layers_mat)



    set_mat_layer_onclick(deck_mat, layers_mat, viz_state)



    deck_mat.setProps({
        onViewStateChange: (params) => on_view_state_change(params, deck_mat, layers_mat, viz_state),
        views: viz_state.views.views_list,
        initialViewState: global_view_state,
        getTooltip: get_tooltip,
        layerFilter: layer_filter,
        layers: get_layers_list(layers_mat),
    })

    el.appendChild(viz_state.root)

}