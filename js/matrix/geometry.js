/**
 * Lay out the matrix, its attribute bars, and its dendrograms in the canvas.
 *
 * The canvas is `total_width/height + height_margin` px (see `ini_deck`).
 * Labels and attribute bars fill `row_region`/`col_region` before the matrix,
 * and each dendrogram strip takes `dendrogram_width` px after it. Every
 * attribute bar adds `*_cat_height + extra_space` px to its region but only
 * shrinks the matrix by `*_cat_offset` px, so with three or more bars on an
 * axis the matrix alone pushed that axis's dendrogram past the canvas edge.
 * The matrix is therefore capped to the space left after the region and the
 * dendrogram; layouts with up to two bars per axis are unchanged.
 */
/** Font size (px) of the row attribute titles (ui/attribute_labels.js). */
export const ROW_ATTR_TITLE_SIZE = 10;

export const compute_geometry = (viz_state) => {
  const { viz } = viz_state;
  const total_row_attrs = viz_state.attr.num.row;
  const total_col_attrs = viz_state.attr.num.col;

  viz.col_region =
    (viz.col_cat_height + viz.extra_space.col) * total_col_attrs +
    viz.col_label;

  viz.row_region =
    (viz.row_cat_width + viz.extra_space.row) * total_row_attrs + viz.row_label;

  const dendro_space = viz.label_buffer + viz.dendrogram_width;

  viz.mat_width = Math.min(
    viz.total_width - viz.row_cat_offset * total_row_attrs,
    viz.total_width + viz.height_margin - viz.row_region - dendro_space
  );
  viz.mat_height = Math.min(
    viz.total_height - viz.col_cat_offset * total_col_attrs,
    viz.total_height + viz.height_margin - viz.col_region - dendro_space
  );

  viz.col_width = viz.mat_width / viz_state.mat.num_cols;
  viz.row_offset = viz.mat_height / viz_state.mat.num_rows;
  viz.col_offset = viz.mat_width / viz_state.mat.num_cols;

  // column category positioning
  viz.cat_shift_col = viz.col_label;
  viz_state.zoom.ini_pan_x = viz.mat_width / 2;
  // not sure why I need to add row_offset?
  viz_state.zoom.ini_pan_y = viz.mat_height / 2 + viz.row_offset;

  // Column labels and attribute bars share the `cols` view, which centers on
  // `label_col_y`. Each bar moves the last bar 9 px down but the view's center
  // only 6.5 px, so from four bars on, the last bar fell below the view. Move
  // the view's target down by that overflow; fewer bars are unchanged.
  // Bar centers follow `build_cat_data_for_axis` (attr_state.js).
  const last_bar_bottom =
    viz.col_cat_offset * (total_col_attrs + 0.5) -
    30 +
    viz.cat_shift_col +
    viz.col_cat_height / 2;
  const bar_overflow =
    viz.col_region / 2 + last_bar_bottom - viz.label_col_y - viz.col_region;
  viz.cols_target_y = viz.label_col_y + Math.max(0, bar_overflow);

  // Row labels and attribute bars share the `rows` view (and the bars' titles
  // the static `row_attr_labels` view), both centered on `rows_target_x`. Each
  // bar moves the last bar 9 px right but the views' right edge only 6.5 px, so
  // from the third bar on, the last bar and its title crossed the edge. Move the
  // target right by that overflow (the content shifts left), counting the bar's
  // half width or its title's half height (10 px text), whichever is larger.
  // Bar centers follow `build_cat_data_for_axis` (attr_state.js) plus
  // `cat_shift_row` (cat_layers.js).
  const last_row_bar_right =
    viz.row_cat_offset * (total_row_attrs - 0.5) +
    20 +
    (viz.cat_shift_row ?? 0) +
    Math.max(viz.row_cat_width / 2, ROW_ATTR_TITLE_SIZE / 2);
  const row_overflow =
    last_row_bar_right - (viz.label_row_x + viz.row_region / 2);
  viz.rows_target_x =
    viz.label_row_x + (total_row_attrs > 0 ? Math.max(0, row_overflow) : 0);
};
