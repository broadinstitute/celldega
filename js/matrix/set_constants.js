export const set_mat_constants = (network, root, width, height) => {

    let viz_state = {}

    /////////////////////////////
    // Constants
    //////////////////////////////

    viz_state.root = root

    viz_state.viz = {}
    viz_state.viz.height_margin = 100

    viz_state.cats = {}
    viz_state.cats.num_cats = {}
    viz_state.cats.num_cats.row = 0
    viz_state.cats.num_cats.col = 0

    viz_state.root.style.height =  ( height + viz_state.viz.height_margin ) + "px"

    viz_state.viz.mat_width = width
    viz_state.viz.mat_height = height

    viz_state.mat = {}
    viz_state.mat.num_rows = network.mat.length
    viz_state.mat.num_cols = network.mat[0].length

    viz_state.row_nodes = network.row_nodes
    viz_state.col_nodes = network.col_nodes

    viz_state.mat.net_mat = network.mat

    viz_state.linkage = network.linkage

    viz_state.viz.base_font_size = 125

    viz_state.viz.col_label = 75 // 40
    viz_state.viz.row_label = 75 // 35

    viz_state.viz.extra_space = {}
    viz_state.viz.extra_space.row = 10
    viz_state.viz.extra_space.col = 10

    viz_state.zoom = {}
    viz_state.zoom.ini_zoom_x = 0
    viz_state.zoom.ini_zoom_y = 0


    viz_state.viz.row_cat_width = 9
    viz_state.viz.col_cat_height = 9

    viz_state.viz.row_cat_offset = 10

    // height of column category bars
    viz_state.viz.col_cat_offset = 10

    // move rows labels left
    viz_state.viz.label_row_x = 15 // 15

    // move col labels up
    viz_state.viz.label_col_y = 25

    viz_state.viz.cat_shift_row = 30

    viz_state.viz.label_buffer = 1

    viz_state.animate = {}
    viz_state.animate.duration = 2500

    viz_state.viz.dendrogram_width = 15

    //////////////////////////////
    // Variables
    //////////////////////////////
    // viz_state.viz.ini_font_size = viz_state.viz.base_font_size / viz_state.mat.num_rows
    viz_state.viz.font_size = {}
    viz_state.viz.font_size.rows = viz_state.viz.base_font_size / viz_state.mat.num_rows
    viz_state.viz.font_size.cols = viz_state.viz.base_font_size / viz_state.mat.num_cols

    viz_state.viz.col_region = (viz_state.viz.col_cat_height + viz_state.viz.extra_space.col) * viz_state.cats.num_cats.col
                                      + viz_state.viz.col_label

    viz_state.viz.row_region = (viz_state.viz.row_cat_width + viz_state.viz.extra_space.row) * viz_state.cats.num_cats.row
                                     + viz_state.viz.row_label

    viz_state.viz.col_width = viz_state.viz.mat_width/viz_state.mat.num_cols
    viz_state.viz.row_offset = viz_state.viz.mat_height/viz_state.mat.num_rows
    viz_state.viz.col_offset = viz_state.viz.mat_width/viz_state.mat.num_cols

    // column category positioning
    viz_state.viz.cat_shift_col = viz_state.viz.col_label // + viz_state.viz.extra_space.col
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

    viz_state.order = {}

    viz_state.order.current = {}
    viz_state.order.current.row = 'clust'
    viz_state.order.current.col = 'clust'

    viz_state.order.new = 'ini'

    viz_state.buttons = {}
    viz_state.buttons.blue = '#8797ff'
    viz_state.buttons.gray = '#EEEEEE'


    return viz_state

}