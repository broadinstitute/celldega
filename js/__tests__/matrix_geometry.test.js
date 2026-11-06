/* global require */

describe('matrix geometry', () => {
  let compute_geometry;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(path.join(__dirname, '../matrix/geometry.js'), 'utf8')
      .replace(/^export const /gm, 'const ');

    ({ compute_geometry } = new Function(
      `${source}\nreturn { compute_geometry };`
    )());
  });

  // Mirrors the layout constants set in matrix/set_constants.js.
  const make_viz_state = ({ row_attrs = 1, col_attrs = 1 } = {}) => ({
    attr: { num: { row: row_attrs, col: col_attrs } },
    mat: { num_rows: 1000, num_cols: 37 },
    zoom: {},
    viz: {
      total_width: 500,
      total_height: 500,
      height_margin: 100,
      row_cat_offset: 9,
      col_cat_offset: 9,
      row_cat_width: 8,
      col_cat_height: 8,
      extra_space: { row: 5, col: 5 },
      row_label: 75,
      col_label: 75,
      label_buffer: 1,
      dendrogram_width: 15,
      label_col_y: 25,
    },
  });

  // Far edge of each dendrogram strip, as positioned in deck-gl/matrix/views.js.
  const dendro_edges = ({ viz }) => ({
    col_bottom:
      viz.col_region + viz.label_buffer + viz.mat_height + viz.dendrogram_width,
    row_right:
      viz.row_region + viz.label_buffer + viz.mat_width + viz.dendrogram_width,
  });

  it.each([1, 2, 3, 6, 10])(
    'keeps both dendrograms inside the canvas with %i attribute bars per axis',
    (num_attrs) => {
      const viz_state = make_viz_state({
        row_attrs: num_attrs,
        col_attrs: num_attrs,
      });
      compute_geometry(viz_state);

      const { col_bottom, row_right } = dendro_edges(viz_state);
      const { viz } = viz_state;
      expect(col_bottom).toBeLessThanOrEqual(
        viz.total_height + viz.height_margin
      );
      expect(row_right).toBeLessThanOrEqual(
        viz.total_width + viz.height_margin
      );
    }
  );

  it('leaves layouts with up to two bars per axis unchanged', () => {
    [0, 1, 2].forEach((num_attrs) => {
      const viz_state = make_viz_state({
        row_attrs: num_attrs,
        col_attrs: num_attrs,
      });
      compute_geometry(viz_state);

      expect(viz_state.viz.mat_width).toBe(500 - 9 * num_attrs);
      expect(viz_state.viz.mat_height).toBe(500 - 9 * num_attrs);
    });
  });

  it('shrinks only the axis with extra bars and updates node sizes', () => {
    const viz_state = make_viz_state({ row_attrs: 1, col_attrs: 6 });
    compute_geometry(viz_state);

    const { viz } = viz_state;
    expect(viz.mat_width).toBe(491);
    expect(viz.mat_height).toBe(500 + 100 - (13 * 6 + 75) - 16);
    expect(viz.row_offset).toBeCloseTo(viz.mat_height / 1000);
    expect(viz.col_width).toBeCloseTo(491 / 37);
    expect(viz_state.zoom.ini_pan_y).toBeCloseTo(
      viz.mat_height / 2 + viz.row_offset
    );
  });

  // The `cols` view centers its target, so a world y lands at
  // col_region / 2 + (y - cols_target_y) inside the view.
  const last_col_bar_bottom_in_view = ({ viz }, num_attrs) => {
    const bar_center =
      viz.col_cat_offset * (num_attrs - 1 + 1.5) - 30 + viz.cat_shift_col;
    return (
      viz.col_region / 2 +
      bar_center +
      viz.col_cat_height / 2 -
      viz.cols_target_y
    );
  };

  it.each([1, 2, 3, 4, 6, 10])(
    'keeps the last of %i column bars inside the cols view',
    (num_attrs) => {
      const viz_state = make_viz_state({ col_attrs: num_attrs });
      compute_geometry(viz_state);

      expect(
        last_col_bar_bottom_in_view(viz_state, num_attrs)
      ).toBeLessThanOrEqual(viz_state.viz.col_region);
    }
  );

  it('only moves the cols view target when bars would overflow', () => {
    [1, 2, 3].forEach((num_attrs) => {
      const viz_state = make_viz_state({ col_attrs: num_attrs });
      compute_geometry(viz_state);
      expect(viz_state.viz.cols_target_y).toBe(25);
    });

    const viz_state = make_viz_state({ col_attrs: 6 });
    compute_geometry(viz_state);
    expect(viz_state.viz.cols_target_y).toBe(31);
  });
});
