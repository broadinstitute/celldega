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
import { alt_slice_linkage, calc_dendro_triangles } from '../matrix/dendro.js';
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

    // console.log(viz_state.linkage)
    // alt_slice_linkage(viz_state, 'row', 0.1)

    var dendro = {};

    dendro.default_level = 5;
    dendro.tri_height = 0.10;
    dendro.trap_height = 0.03;
    dendro.trap_float = 0.005;

    dendro.dendro_args = {};
    dendro.group_level = {};
    dendro.update_dendro = false;

    dendro.selected_clust_names = []

    dendro.group_info = {};

    dendro.default_link_level = 0.5

    dendro.output_label_format = 'list'

    dendro.min_dist = {}
    dendro.min_dist.row = 0 // 0.75
    dendro.min_dist.col = 0 // 0.75

    let axes = ['col', 'row']

    let link_mat
    dendro.max_linkage_dist = {}
    let dist_thresh

    axes.forEach((axis) => {
      link_mat = viz_state.linkage[axis]
      dendro.max_linkage_dist[axis] = link_mat[link_mat.length-1][2] + 0.01
      dist_thresh = dendro.max_linkage_dist[axis] * dendro.default_link_level

      // alternate linkage slicing code
      alt_slice_linkage(viz_state, axis, dist_thresh)

      dendro.group_info[axis] = calc_dendro_triangles(viz_state, dendro, axis)

    })

    console.log(dendro.group_info)

    viz_state.dendro = dendro

    // console.log('row and col nodes after linkage slicing')
    // console.log(viz_state.row_nodes)
    // console.log(viz_state.col_nodes)

    let layers_mat = {}
    layers_mat.mat_layer = ini_mat_layer(viz_state)
    layers_mat.row_label_layer = ini_row_label_layer(viz_state)
    layers_mat.col_label_layer = ini_col_label_layer(viz_state)
    layers_mat.row_cat_layer = ini_row_cat_layer(viz_state)
    layers_mat.col_cat_layer = ini_col_cat_layer(viz_state)


    // dendrogram triangle layers
    const triangleHeight = 50; // Uniform height for all triangles
    const polygons = {};

    // Generate polygons for "col" and "row" axes
    ['col', 'row'].forEach((axis) => {

        polygons[axis] = [];

        dendro.group_info[axis].forEach((group) => {
        const { pos_top, pos_bot, pos_mid } = group;

        if (axis === 'col') {
            // Column dendrogram - bottom of the heatmap, pointing down
            const width = (pos_bot - pos_top) / 2;

            // Triangle vertices
            const triangle = [
            [pos_mid, pos_bot + triangleHeight], // Bottom vertex (pointing downward)
            [pos_mid - width, pos_bot], // Top-left of the base
            [pos_mid + width, pos_bot], // Top-right of the base
            ];

            polygons[axis].push({
            coordinates: triangle,
            properties: { ...group, axis }, // Attach group data and axis
            });
        } else if (axis === 'row') {
            // Row dendrogram - right side of the heatmap, pointing outward (right)
            const height = (pos_bot - pos_top) / 2;

            // Triangle vertices
            const triangle = [
            [pos_bot + triangleHeight, pos_mid], // Right vertex (pointing outward)
            [pos_bot, pos_mid - height], // Top-left of the base
            [pos_bot, pos_mid + height], // Bottom-left of the base
            ];

            polygons[axis].push({
            coordinates: triangle,
            properties: { ...group, axis }, // Attach group data and axis
            });
        }
        });
    });

    // console.log(polygons)

    ['col', 'row'].forEach((axis) => {

        layers_mat[axis + '_dendro'] = new PolygonLayer({
            id: axis + '-dendro-layer',
            data: polygons[axis],
            getPolygon: (d) => d.coordinates, // Access triangle coordinates
            getFillColor: (d) => (d.axis === 'col' ? [0, 0, 255, 128] : [255, 0, 0, 128]), // Different colors for rows/cols
            getLineColor: [255, 255, 255, 255], // White outline
            lineWidthMinPixels: 1,
            pickable: true, // Enable interactivity
            autoHighlight: true, // Highlight on hover
            onHover: ({ object }) => console.log(object?.properties), // Hover info
        });

    })

    console.log(layers_mat)

    ini_views(viz_state)

    const global_view_state = ini_view_state(viz_state)

    set_mat_layer_onclick(deck_mat, layers_mat, viz_state)
    set_row_label_layer_onclick(deck_mat, layers_mat, viz_state)
    set_col_label_layer_onclick(deck_mat, layers_mat, viz_state)

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