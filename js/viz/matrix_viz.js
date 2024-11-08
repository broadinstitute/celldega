import { ini_deck } from '../deck-gl/matrix/deck_mat.js'
import { CustomMatrixLayer } from '../deck-gl/matrix/custom_matrix_layer.js'
// import { mat_layer } from '../deck-gl/matrix/matrix_layers.js';
import { set_mat_data } from '../matrix/mat_data.js';

import { TextLayer, OrthographicView, Layer } from 'deck.gl';
// import { index } from 'd3';
import * as d3 from 'd3'

export const matrix_viz = async (
    model,
    el,
    network,
    width,
    height
    // token,
) => {

    let viz_state = {}

    viz_state.root = document.createElement("div")

    viz_state.viz = {}
    viz_state.viz.height_margin = 100

    viz_state.root.style.height =  ( height + viz_state.viz.height_margin ) + "px"

    let deck_mat = ini_deck(viz_state.root)

    console.log('hello')

    /////////////////////////////
    // Constants
    //////////////////////////////
    viz_state.viz.mat_width = width
    viz_state.viz.mat_height = height

    viz_state.mat = {}
    viz_state.mat.num_rows = network.mat.length
    viz_state.mat.num_cols = network.mat[0].length

    viz_state.viz.base_font_size = 100

    viz_state.viz.col_label_height = 20
    viz_state.viz.row_region_width = 90

    viz_state.viz.extra_height_col = 20

    viz_state.zoom = {}
    viz_state.zoom.ini_zoom_x = 0
    viz_state.zoom.ini_zoom_y = 0

    viz_state.viz.row_label_width = 30

    viz_state.viz.row_cat_width = 9
    viz_state.viz.col_cat_height = 9

    // width of row category bars
    viz_state.viz.row_cat_offset = 10

    viz_state.cat = {}
    viz_state.cat.num_cats_col = 2

    // height of column category bars
    viz_state.viz.col_cat_offset = 10

    // position the cats
    viz_state.viz.label_row_x = 15
    viz_state.viz.label_col_y = 25

    viz_state.viz.cat_shift_row = 30

    viz_state.viz.label_buffer = 1

    //////////////////////////////
    // Variables
    //////////////////////////////
    viz_state.viz.ini_font_size = viz_state.viz.base_font_size / viz_state.mat.num_rows

    viz_state.viz.inst_font_size = viz_state.viz.ini_font_size

    // const row_height = viz_state.viz.mat_height/viz_state.mat.num_rows
    viz_state.viz.col_region_height = viz_state.viz.col_cat_height * viz_state.cat.num_cats_col + viz_state.viz.col_label_height + viz_state.viz.extra_height_col
    viz_state.viz.col_width = viz_state.viz.mat_width/viz_state.mat.num_cols
    viz_state.viz.row_offset = viz_state.viz.mat_height/viz_state.mat.num_rows
    viz_state.viz.col_offset = viz_state.viz.mat_width/viz_state.mat.num_cols


    // column category positioning
    viz_state.viz.cat_shift_col = viz_state.viz.col_label_height // + viz_state.viz.extra_height_col
    viz_state.zoom.ini_pan_x = viz_state.viz.mat_width/2

    // not sure why I need to add row_offset?
    viz_state.zoom.ini_pan_y = viz_state.viz.mat_height/2 + viz_state.viz.row_offset

    // make mat_data from network_data
    //////////////////////////////////////

    // Assuming network.mat is an array of arrays
    viz_state.mat.mat_data = [];
    viz_state.mat.num_rows = network.mat.length;
    viz_state.mat.num_cols = network.mat[0].length;

    viz_state.mat.max_abs_value = network.mat.flat().reduce((max, num) => Math.max(max, Math.abs(num)), -Infinity);



    set_mat_data(network, viz_state)


    // col label data
    let matrix_index = 0;

    let col_label_data = []
    network.col_nodes.forEach((node, index) => {
        const p = {
            position: [viz_state.viz.col_width * (index + 3/4), viz_state.viz.col_label_height/2],
            name: node.name
        };
        col_label_data.push(p);
    })

    console.log(col_label_data)

    console.log('here')

    let row_label_data = []
    network.row_nodes.forEach((node, index) => {
        const p = {
            position: [
                viz_state.viz.row_label_width / 2,
                viz_state.viz.row_offset * (index + 1.5)
              ],
            name: node.name
        };
        row_label_data.push(p);
    })

    // row cat data
    matrix_index = 0;

    var index_row = 0
    const num_row_cats = 3

    var num_points = viz_state.mat.num_rows * num_row_cats

    const row_cat_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_row_cats

        if (matrix_index % num_row_cats === 0){
        index_row += 1;
        }

        const p = {
            position: [viz_state.viz.row_cat_offset * (index_col + 0.5), viz_state.viz.row_offset * (index_row + 0.5)],
            color: [0, 255, 0, 255],
            name: 'something ' + index_row
        };

        matrix_index += 1;

        return p;
    });

    // col cat data

    matrix_index = 0;

    var index_row = 0

    var num_points = viz_state.cat.num_cats_col * viz_state.mat.num_cols

    const col_cat_data = new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % viz_state.mat.num_cols

        if (matrix_index % viz_state.mat.num_cols === 0){
        index_row += 1;
        }

        const p = {
            position: [viz_state.viz.col_offset * (index_col + 0.5), viz_state.viz.col_cat_offset * (index_row + 0.5)],
            color: [0, 255, 0, 150],
            name: 'some column ' + index_col,
        };

        matrix_index += 1;

        return p;
    });

    // // animation transition function
    // // https://observablehq.com/@cornhundred/deck-gl-instanced-scatter-test
    // const transitions = ({
    //     getPosition: {
    //       duration: 3000,
    //       easing: d3.easeCubic
    //     }
    // })


    // Create a new ScatterplotLayer using the input data
    const mat_layer = new CustomMatrixLayer({
        id: 'matrix-layer',
        data: viz_state.mat.mat_data,
        getPosition: d => d.position, // Position of each point
        getFillColor: d => d.color,   // Color of each point
        pickable: true,               // Enable picking for interactivity
        opacity: 0.8,                  // Set the opacity of the points
        antialiasing: false,
        tile_height: viz_state.viz.mat_height/viz_state.mat.num_rows * 0.5,
        tile_width: viz_state.viz.mat_height/viz_state.mat.num_cols * 0.5

    });

    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: row_label_data, // This should be the same data source you used for your other layers
        getPosition: d => d.position,
        getText: d => d.name, // Replace 'label' with the property in your data that contains the text you want to display
        getSize: d => viz_state.viz.inst_font_size,
        getColor: [0, 0, 0], // Text color as an RGBA array
        getAngle: 0, // Optional: Text angle in degrees
        getTextAnchor: 'end', // middle
        getAlignmentBaseline: 'center',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        updateTriggers: {
          getSize: viz_state.viz.inst_font_size
        },
        pickable: true,
        // onHover: (info, event) => console.log('Hovered:', info), // , event
      })


    const col_label_layer  = new TextLayer({
        id: 'col-label-layer',
        data: col_label_data, // This should be the same data source you used for your other layers
        getPosition: d => d.position,
        getText: d => d.name,
        getSize: viz_state.viz.inst_font_size,
        getColor: [0, 0, 0], // Text color as an RGBA array
        getAngle: 45, // Optional: Text angle in degrees
        getTextAnchor: 'start', // middle
        getAlignmentBaseline: 'bottom',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        updateTriggers: {
          getSize: viz_state.viz.inst_font_size
        },
        pickable: true,
        // onHover: (info, event) => console.log('Hovered:', info), // , event
      })

    // Create a new ScatterplotLayer using the input data
    const row_cat_layer = new CustomMatrixLayer({
        id: 'row-layer',
        data: row_cat_data,
        // getPosition: d => d.position, // Position of each point
        getPosition: d => [d.position[0] + viz_state.viz.cat_shift_row, d.position[1]],
        getFillColor: d => d.color,   // Color of each point
        pickable: true,               // Enable picking for interactivity
        opacity: 0.8,                  // Set the opacity of the points
        tile_width: viz_state.viz.row_cat_width/2 * 0.9,
        tile_height: viz_state.viz.mat_height/viz_state.mat.num_rows * 0.5,
    });

    // Create a new ScatterplotLayer using the input data
    const col_cat_layer = new CustomMatrixLayer({
        id: 'col-layer',
        data: col_cat_data,
        getPosition: d => [d.position[0], d.position[1] + viz_state.viz.cat_shift_col],
        getFillColor: d => d.color,   // Color of each point
        pickable: true,               // Enable picking for interactivity
        opacity: 0.8,                  // Set the opacity of the points
        tile_width: viz_state.viz.mat_height/viz_state.mat.num_cols * 0.5 ,
        tile_height: viz_state.viz.col_cat_height/2,

    });


    const layers = [mat_layer, row_cat_layer, col_cat_layer, row_label_layer, col_label_layer]

    const views = [

        new OrthographicView({
          id: 'matrix',
          x: ( viz_state.viz.row_region_width + viz_state.viz.label_buffer) + 'px',
          y: ( viz_state.viz.col_region_height + viz_state.viz.label_buffer) + 'px',
          width: viz_state.viz.mat_width + 'px',
          height: viz_state.viz.mat_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'all'},
        }),

        new OrthographicView({
          id: 'rows',
          x: '0px',
          y: (viz_state.viz.col_region_height + viz_state.viz.label_buffer) + 'px',
          width: viz_state.viz.row_region_width + 'px',
          height: viz_state.viz.mat_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'Y'},
        }),

        new OrthographicView({
          id: 'cols',
          x: (viz_state.viz.row_region_width + viz_state.viz.label_buffer) + 'px',
          y: '0px',
          width: viz_state.viz.mat_width + 'px',
          height: viz_state.viz.col_region_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'X'},
        }),

  ]


    // update zoom_data inplace
    // this takes as an input the mutable zoom_data
    const update_zoom_data = (zoom_data, viewId, zoom, target) => {

        if (viewId === 'matrix') {

            // update pans
            zoom_data.pan_x = target[0];
            zoom_data.pan_y = target[1];

            // update zooms
            zoom_data.zoom_x = zoom[0]
            zoom_data.zoom_y = zoom[1]

        } else if (viewId === 'cols') {

            console.log('cols')

            // update pan_x
            zoom_data.pan_x = target[0]

            // update zooms
            zoom_data.zoom_x = zoom[0]

            // // switch to y zoom
            // ////////////////////////
            // // update pan_x
            // zoom_data.pan_x = target[0]

            // // update zooms
            // zoom_data.zoom_y = zoom[1]

        } else if (viewId === 'rows') {

            console.log('rows')

            // update pan_y
            zoom_data.pan_y = target[1];

            // update zooms
            zoom_data.zoom_y = zoom[1]

        }
    }

    const ini_global_view_state = () => {

        let globalViewState = {
          matrix: {
            target: [viz_state.zoom.ini_pan_x, viz_state.zoom.ini_pan_y],
            zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
          },
          rows: {
            target: [viz_state.viz.label_row_x, viz_state.zoom.ini_pan_y],
            zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
          },
          cols: {
            target: [viz_state.zoom.ini_pan_x, viz_state.viz.label_col_y],
            zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
          },
        }

        return globalViewState

      }


    const layerFilter = ({layer, viewport}) => {

        // console.log(viewport.id, layer.id)
        if (viewport.id === 'matrix' && layer.id === 'matrix-layer'){
            return true
        } else if (viewport.id === 'rows' && layer.id === 'row-layer'){
            return true
        } else if (viewport.id === 'cols' && layer.id === 'col-layer'){
            return true
        } else if (viewport.id === 'rows' && layer.id === 'row-label-layer'){
            return true
        } else if (viewport.id === 'cols' && layer.id === 'col-label-layer'){
            return true
        }

        return false

        // return true
    }

    const getTooltip = ({object, layer}) => {
        if (object) {
          // Check which layer the tooltip is currently over
          if (layer.id === 'row-label-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Row Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'col-label-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Col Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'row-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Row Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'col-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Col Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'matrix-layer') {
            // Display the default tooltip for other layers
            return {
              html: `Row: ${object.row} <br> Column: ${object.col}`,
              style: {color: "white"},
            };
          }
        }
      }


    // trying to define a mutable zoom_data outside of the deckgl cell
    let zoom_data = ({
        pan_x: viz_state.zoom.ini_pan_x,
        pan_y: viz_state.zoom.ini_pan_y,
        zoom_x: viz_state.zoom.ini_zoom_x,
        zoom_y: viz_state.zoom.ini_zoom_y,
    })


    const ini_view_state = ini_global_view_state()

    const curate_pan_y = (target_y, zoom_curated_y, ini_pan_y) => {

        var pan_curated_y

        var zoom_factor_y = Math.pow(2, zoom_curated_y)

        var min_pan_y = (ini_pan_y - viz_state.viz.row_offset)/zoom_factor_y + viz_state.viz.row_offset

        // calculating the shift to the min, to re-use for the max
        var min_diff = ini_pan_y - min_pan_y

        var max_pan_y = ini_pan_y + min_diff

        if (target_y <= min_pan_y){
          // console.log('below min')
          pan_curated_y = min_pan_y
        } else if (target_y > max_pan_y) {
          pan_curated_y = max_pan_y
          // console.log('above min')
        } else {
          pan_curated_y = target_y
          // console.log('within bounds')
        }

        return pan_curated_y
      }

    const curate_pan_x = (target_x, zoom_curated_x, ini_pan_x) => {

        var pan_curated_x

        var zoom_factor_x = Math.pow(2, zoom_curated_x)

        var min_pan_x = ini_pan_x/zoom_factor_x

        // calculating the shift to the min, to re-use for the max
        var min_diff = ini_pan_x - min_pan_x

        var max_pan_x = ini_pan_x + min_diff

        if (target_x <= min_pan_x){
            // console.log('below min')
            pan_curated_x = min_pan_x
        } else if (target_x > max_pan_x) {
            pan_curated_x = max_pan_x
            // console.log('above min')
        } else {
            pan_curated_x = target_x
            // console.log('within bounds')
        }

        return pan_curated_x

    }


    // new version with fewer arguments
    // this does not need the mutable zoom_data since it
    // is not going to be modifying zoom_data
    const redefine_global_view_state = (zoom_data, viewId, zoom, target) => {

        var globalViewState

        var min_zoom_x = 0
        var min_zoom_y = 0
        var zoom_curated_x = Math.max(min_zoom_x, zoom[0])
        var zoom_curated_y = Math.max(min_zoom_x, zoom[1])

        var pan_curated_x = curate_pan_x(target[0], zoom_curated_x, viz_state.zoom.ini_pan_x)
        var pan_curated_y = curate_pan_y(target[1], zoom_curated_y, viz_state.zoom.ini_pan_y)

        if (viewId === 'matrix') {

            globalViewState = {
                matrix: {
                    zoom: [zoom_curated_x, zoom_curated_y],
                    target: [pan_curated_x, pan_curated_y]
                },
                rows:   {
                    zoom: [viz_state.zoom.ini_zoom_x, zoom_curated_y],
                    target: [viz_state.viz.label_row_x, pan_curated_y]
                },
                cols:   {
                    zoom: [zoom_curated_x, viz_state.zoom.ini_zoom_y],
                    target: [pan_curated_x, viz_state.viz.label_col_y]
                },
            }

        } else if (viewId === 'cols'){

            globalViewState = {
                matrix: {
                    zoom: [zoom_curated_x, zoom_data.zoom_y],
                    target: [pan_curated_x, zoom_data.pan_y]
                },
                rows:   {
                    zoom: [viz_state.zoom.ini_zoom_x, zoom_data.zoom_y],
                    target: [viz_state.viz.label_row_x, zoom_data.pan_y]
                },
                cols:   {
                    zoom: [zoom_curated_x, viz_state.zoom.ini_zoom_y],
                    target: [pan_curated_x, viz_state.viz.label_col_y]
                },
            }

        } else if (viewId === 'rows'){

            globalViewState = {
                matrix: {
                    zoom: [zoom_data.zoom_x, zoom_curated_y],
                    target: [zoom_data.pan_x, pan_curated_y]
                },
                rows:   {
                    zoom: [viz_state.zoom.ini_zoom_x, zoom_curated_y],
                    target: [viz_state.viz.label_row_x, pan_curated_y]
                },
                cols:   {
                    zoom: [zoom_data.zoom_x, viz_state.zoom.ini_zoom_y],
                    target: [zoom_data.pan_x, viz_state.viz.label_col_y]
                },
            }

        }

        return globalViewState
    }


    const on_view_state_change = ({viewState, viewId}) => {

        const {zoom, target, offset} = viewState;

        // this takes the latest non-mutable zoom_data since it does
        // not update zoom_data
        var global_view_state = redefine_global_view_state(zoom_data, viewId, zoom, target)

        var zoom_factor_x = Math.pow(2, zoom_data.zoom_x)

        viz_state.viz.inst_font_size = viz_state.viz.ini_font_size * zoom_factor_x

        // console.log('viz_state.viz.inst_font_size', viz_state.viz.inst_font_size)

        // this takes mutable zoom_data since it updates zoom_data's state
        update_zoom_data(zoom_data, viewId, zoom, target)

        var updated_view_state = {...global_view_state}

        // this will only update the zoom state for the current layer
        // return updated_view_state

        // use setProps to update viewState with updated_view_state
        deck_mat.setProps({viewState: updated_view_state});

    }

    deck_mat.setProps({
        onViewStateChange: on_view_state_change,
        views: views,
        initialViewState: ini_view_state,
        getTooltip: getTooltip,
        layerFilter: layerFilter,
        layers: layers,
    })

    el.appendChild(viz_state.root)

}