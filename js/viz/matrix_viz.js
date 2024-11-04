import { ini_deck } from '../deck-gl/deck_mat.js'

import { ScatterplotLayer } from 'deck.gl';

export const matrix_viz = async (
    model,
    el,
    // token,
) => {
    console.log('matrix_viz!!!!!!!!!')
    console.log('model', model)
    console.log('el', el)


    let viz_state = {}


    // Create and append the visualization.
    let root = document.createElement("div")
    root.style.height = "800px"

    let deck_mat = ini_deck(root)

    console.log('deck_mat')
    console.log(deck_mat)

    //////////////////////////////
    // Constants
    //////////////////////////////
    const mat_width = 600
    const mat_height = 600

    const num_rows = 10
    const num_cols = 10

    const base_font_size = 100

    const col_label_height = 20
    const row_region_width = 90

    const extra_height_col = 20

    const ini_zoom_x = 0

    const row_label_width = 30

    const row_cat_width = 9
    const col_cat_height = 9

    // width of row category bars
    const row_cat_offset = 10

    const num_cats_col = 3

    // height of column category bars
    const col_cat_offset = 10

    // position the cats
    const label_row_x = 15

    // position the cats
    const label_col_y = 25

    const cat_shift_row = 30

    const label_buffer = 1

    const ini_zoom_y = 0

    //////////////////////////////
    // Variables
    //////////////////////////////
    const ini_font_size = base_font_size / num_rows

    let inst_font_size = ini_font_size

    const row_height = mat_height/num_rows
    const col_region_height = col_cat_height * num_cats_col + col_label_height + extra_height_col
    const col_width = mat_width/num_cols
    const row_offset = mat_height/num_rows
    const col_offset = mat_width/num_cols


    // column category positioning
    const cat_shift_col = col_label_height // + extra_height_col
    const ini_pan_x = mat_width/2

    // not sure why I need to add row_offset?
    const ini_pan_y = mat_height/2 + row_offset

    const viz_width = mat_width + row_region_width

    const viz_height = mat_height + col_region_height

    //////////////////////////////
    // Data
    //////////////////////////////
    let matrix_index = 0;

    var index_row = 0

    var num_points = num_rows * num_cols

    // mat data
    const mat_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_cols

        if (matrix_index % num_cols === 0){
        index_row += 1;
        }

        var inst_red = parseInt(255 * (index_row/num_rows))
        var inst_blue = parseInt(255 * (index_col/num_cols))

        var inst_color
        if (index_col >= index_row){
        inst_color = [0, 0, 255]
        } else {
        inst_color = [255, 0, 0]
        }

        var inst_opacity = parseInt(255 * matrix_index/num_points)

        const p = {
        position: [col_offset * index_col + col_offset/2, row_offset * index_row + row_offset/2],
        color: [inst_color[0], inst_color[1], inst_color[2], inst_opacity],
        value: ((index_row/num_rows) + (index_col/num_cols))/2,
        row: index_row,
        // seem to need to add index to col
        col: index_col + 1,
        };

        matrix_index += 1;

        return p;
    });

    // col label data
    matrix_index = 0;

    var index_col = 0

    var num_points = num_rows * 1

    const col_label_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_cols

        if (matrix_index % 1  === 0){
        index_col += 1;
        }

        const p = {
        position: [col_width * index_col - col_offset/2, col_label_height],
        name: 'col-' + index_col
        };

        matrix_index += 1;

        return p;
    });


    // row label data

    matrix_index = 0;

    var index_row = 0
    // const num_row_cats = 1

    var num_points = num_rows// * num_row_cats

    const row_label_data = new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % 1 // num_row_cats

        if (matrix_index % 1 == 0){ // num_row_cats =
        index_row += 1;
        }

        const p = {
        position: [row_label_width , row_offset * index_row + row_offset/2],
        name: 'row-' + index_row
        };

        matrix_index += 1;

        return p;
    });


    // row cat data
    matrix_index = 0;

    var index_row = 0
    const num_row_cats = 3

    var num_points = num_rows * num_row_cats

    const row_cat_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_row_cats

        if (matrix_index % num_row_cats === 0){
        index_row += 1;
        }

        const p = {
        position: [row_cat_offset * index_col, row_offset * index_row],
        color: [0, 255, 0, 255],
        name: 'something'
        };

        matrix_index += 1;

        return p;
    });

    // col cat data

    matrix_index = 0;

    var index_row = 0

    var num_points = num_cats_col * num_cols

    const col_cat_data = new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_cols

        if (matrix_index % num_cols === 0){
        index_row += 1;
        }

        const p = {
        position: [col_offset * index_col, col_cat_offset * index_row],
        color: [0, 255, 0, 150],
        name: 'some column',
        };

        matrix_index += 1;

        return p;
    });

    class SquareScatterplotLayer extends ScatterplotLayer {
        getShaders() {
          // Get the default shaders from ScatterplotLayer
          const shaders = super.getShaders();

          // Customize the fragment shader to create square-shaped points
          shaders.fs = `#version 300 es
          #define SHADER_NAME scatterplot-layer-fragment-shader
          precision highp float;
          in vec4 vFillColor;
          in vec2 unitPosition;
          out vec4 fragColor;
          void main(void) {
              geometry.uv = unitPosition;
              fragColor = vFillColor;
              DECKGL_FILTER_COLOR(fragColor, geometry);
          }`;

          return shaders;
        }
      }




}