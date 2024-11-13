export const set_mat_constants = (network, root, width, height) => {

    let viz_state = {}

    /////////////////////////////
    // Constants
    //////////////////////////////

    viz_state.root = root

    viz_state.viz = {}
    viz_state.viz.height_margin = 100

    viz_state.root.style.height =  ( height + viz_state.viz.height_margin ) + "px"

    viz_state.viz.mat_width = width
    viz_state.viz.mat_height = height

    viz_state.mat = {}
    viz_state.mat.num_rows = network.mat.length
    viz_state.mat.num_cols = network.mat[0].length

    viz_state.viz.base_font_size = 125

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

    viz_state.cats = {}
    viz_state.cats.num_cats_col = 2

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

    viz_state.viz.col_region_height = viz_state.viz.col_cat_height * viz_state.cats.num_cats_col + viz_state.viz.col_label_height + viz_state.viz.extra_height_col
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

    return viz_state

}