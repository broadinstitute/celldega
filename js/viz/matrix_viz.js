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

import { ini_deck } from '../deck-gl/matrix/deck_mat.js'
import { set_mat_data } from '../matrix/mat_data.js';
import { set_mat_constants } from '../matrix/set_constants.js';
import { set_row_label_data, set_col_label_data } from '../matrix/label_data.js';
import { set_row_cat_data, set_col_cat_data } from '../matrix/cat_data.js';
import { ini_mat_layer, set_mat_layer_onclick } from '../deck-gl/matrix/mat_layer.js';
import { ini_row_label_layer, ini_col_label_layer, set_row_label_layer_onclick, set_col_label_layer_onclick } from '../deck-gl/matrix/label_layers.js';
import { ini_row_cat_layer, ini_col_cat_layer } from '../deck-gl/matrix/cat_layers.js';
import { get_mat_layers_list, layer_filter } from '../deck-gl/matrix/matrix_layers.js'
import { ini_views, ini_view_state } from '../deck-gl/matrix/views.js'
import { on_view_state_change } from '../deck-gl/matrix/on_view_state_change.js'
import { ini_zoom_data } from '../deck-gl/matrix/zoom.js'
import { get_tooltip } from '../deck-gl/matrix/matrix_tooltip.js'
import { make_matrix_ui_container } from '../ui/ui_containers.js';
import { calc_dendro_polygons, ini_dendro } from '../matrix/dendro.js';
import { PolygonLayer } from 'deck.gl'

export const matrix_viz = async (
    model,
    el,
    network,
    width,
    height
    // token,
) => {

    const root = document.createElement("div")
    root.style.border = "1px solid #d3d3d3"
    let deck_mat = ini_deck(root)

    let viz_state = set_mat_constants(network, root, width, height)
    viz_state.el = el

    console.log(network)

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

    let layers_mat = {}
    layers_mat.mat_layer = ini_mat_layer(viz_state)
    layers_mat.row_label_layer = ini_row_label_layer(viz_state)
    layers_mat.col_label_layer = ini_col_label_layer(viz_state)
    layers_mat.row_cat_layer = ini_row_cat_layer(viz_state)
    layers_mat.col_cat_layer = ini_col_cat_layer(viz_state)


    // dendrogram triangle layers
    const triangleHeight = 500; // Uniform height for all triangles
    const polygons = {};

    // need semicolon for some reason
    calc_dendro_polygons(viz_state, 'row');
    calc_dendro_polygons(viz_state, 'col');



    const ini_dendro_layer = (layers_mat, viz_state, axis) => {

        const inst_layer = new PolygonLayer({
            id: axis + '-dendro-layer',
            data: viz_state.dendro.polygons[axis],
            getPolygon: (d) => d.coordinates,
            getFillColor: [0, 0, 0, 90],
            getLineColor: [255, 255, 255, 255],
            lineWidthMinPixels: 0,
            pickable: true,
            // autoHighlight: true, // Highlight on hover
            // onHover: ({ object }) => console.log(object?.properties.name), // Hover info
        })

        return inst_layer

    }

    layers_mat['row_dendro_layer'] = ini_dendro_layer(layers_mat, viz_state, 'row')
    layers_mat['col_dendro_layer'] = ini_dendro_layer(layers_mat, viz_state, 'col')


    console.log('layers_mat')
    console.log(layers_mat)

    ini_views(viz_state)

    const global_view_state = ini_view_state(viz_state)

    set_mat_layer_onclick(deck_mat, layers_mat, viz_state)
    set_row_label_layer_onclick(deck_mat, layers_mat, viz_state)
    set_col_label_layer_onclick(deck_mat, layers_mat, viz_state)

    console.log('layers_list')
    console.log(get_mat_layers_list(layers_mat))

    deck_mat.setProps({
        onViewStateChange: (params) => on_view_state_change(params, deck_mat, layers_mat, viz_state),
        views: viz_state.views.views_list,
        initialViewState: global_view_state,
        getTooltip: (params) =>  get_tooltip(viz_state, params),
        layerFilter: layer_filter,
        layers: get_mat_layers_list(layers_mat),
    })

    const ui_container = make_matrix_ui_container(deck_mat, layers_mat, viz_state)


    // slider
    viz_state.dendro.sliders = {}
    viz_state.dendro.sliders.row = document.createElement("input")
    viz_state.dendro.sliders.row.type = "range"
    viz_state.dendro.sliders.row.min = "0"
    viz_state.dendro.sliders.row.max = "100"
    viz_state.dendro.sliders.row.value = 50
    viz_state.dendro.sliders.row.className = "slider"
    viz_state.dendro.sliders.row.style.width = "75px"
    // viz_state.dendro.sliders.row.addEventListener("input", () => console.log('here'))

    // Add event listener to log the slider value
    viz_state.dendro.sliders.row.addEventListener("input", (event) => {
        console.log(`Slider value: ${event.target.value}`);
        console.log('viz_state', viz_state)


    });

    ui_container.appendChild(viz_state.dendro.sliders.row)


    el.appendChild(ui_container)
    el.appendChild(viz_state.root)


}