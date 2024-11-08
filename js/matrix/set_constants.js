export const set_mat_constants = (network, viz_state, root, width, height) => {
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
}