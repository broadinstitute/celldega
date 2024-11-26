// The Celldega Matrix Vizualization Method is being built using the approaches
// and code adaptations from the Clustergrammer-GL library, which is available at
// github.com/ismms-himc/clustergrammer-gl
// and being used under the license
//
// MIT License

// Copyright (c) 2021 Nicolas Fernandez

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

import { ini_deck } from '../deck-gl/matrix/deck_mat'
import { set_mat_data } from '../matrix/mat_data'
import { set_mat_constants } from '../matrix/set_constants'
import { set_row_label_data, set_col_label_data } from '../matrix/label_data'
import { set_row_cat_data, set_col_cat_data } from '../matrix/cat_data'
import { ini_mat_layer, set_mat_layer_onclick } from '../deck-gl/matrix/mat_layer'
import { ini_row_label_layer, ini_col_label_layer, set_row_label_layer_onclick, set_col_label_layer_onclick } from '../deck-gl/matrix/label_layers'
import { ini_row_cat_layer, ini_col_cat_layer } from '../deck-gl/matrix/cat_layers';
import { get_mat_layers_list, layer_filter } from '../deck-gl/matrix/matrix_layers'
import { ini_views, ini_view_state } from '../deck-gl/matrix/views'
import { on_view_state_change } from '../deck-gl/matrix/on_view_state_change'
import { ini_zoom_data } from '../deck-gl/matrix/zoom'
import { get_tooltip } from '../deck-gl/matrix/matrix_tooltip'
import { make_matrix_ui_container } from '../ui/ui_containers';
import { calc_dendro_polygons, ini_dendro } from '../matrix/dendro';
import { ini_dendro_layer, set_dendro_layer_onclick } from '../deck-gl/matrix/dendro_layers'

export const matrix_viz = async (
    model,
    el,
    network,
    width='800',
    height='800',
    row_label_callback=null,
    col_label_callback=null,
    col_dendro_callback=null
) => {

    const root = document.createElement("div")
    root.style.border = "1px solid #d3d3d3"
    // root.style.width = width
    let deck_mat = ini_deck(root, width, height)

    let viz_state = set_mat_constants(
        model,
        network,
        root,
        width,
        height,
        row_label_callback,
        col_label_callback,
        col_dendro_callback
    )
    // fix for tooltip positioning
    el.style.position = 'relative'
    viz_state.el = el

    set_mat_data(network, viz_state)

    viz_state.labels = {}

    viz_state.labels.clicks = {}

    ini_zoom_data(viz_state)

    viz_state.mat.orders = {}

    set_row_label_data(network, viz_state)
    set_col_label_data(network, viz_state)

    viz_state.cats.row_cat_data = set_row_cat_data(network, viz_state)
    viz_state.cats.col_cat_data = set_col_cat_data(network, viz_state)

    ini_dendro(viz_state)

    // need semicolon for some reason
    calc_dendro_polygons(viz_state, 'row');
    calc_dendro_polygons(viz_state, 'col');

    let layers_mat = {}
    layers_mat.mat_layer = ini_mat_layer(viz_state)
    layers_mat.row_label_layer = ini_row_label_layer(viz_state)
    layers_mat.col_label_layer = ini_col_label_layer(viz_state)
    layers_mat.row_cat_layer = ini_row_cat_layer(viz_state)
    layers_mat.col_cat_layer = ini_col_cat_layer(viz_state)
    layers_mat.row_dendro_layer = ini_dendro_layer(layers_mat, viz_state, 'row')
    layers_mat.col_dendro_layer = ini_dendro_layer(layers_mat, viz_state, 'col')

    ini_views(viz_state)

    const global_view_state = ini_view_state(viz_state)

    set_mat_layer_onclick(deck_mat, layers_mat, viz_state)
    set_row_label_layer_onclick(deck_mat, layers_mat, viz_state)
    set_col_label_layer_onclick(deck_mat, layers_mat, viz_state)
    set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, 'row')
    set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, 'col')

    deck_mat.setProps({
        onViewStateChange: (params) => on_view_state_change(params, deck_mat, layers_mat, viz_state),
        views: viz_state.views.views_list,
        initialViewState: global_view_state,
        getTooltip: (params) =>  get_tooltip(viz_state, params),
        layerFilter: layer_filter,
        layers: get_mat_layers_list(layers_mat),
    })

    const ui_container = make_matrix_ui_container(deck_mat, layers_mat, viz_state)

    el.appendChild(ui_container)
    el.appendChild(viz_state.root)


}