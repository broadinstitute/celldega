/* global require */

describe('redefine_global_view_state', () => {
  let redefine_global_view_state;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/redefine_global_view_state.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const shims = `
      const get_dendro_tree_view_states = (viz_state, zoom, pan) => ({
        dendro_tree_static: {
          target: [viz_state.viz.mat_width / 2, viz_state.viz.mat_height / 2],
          zoom: [0, 0],
        },
        dendro_tree_rows: {
          target: [viz_state.viz.mat_width / 2, pan[1]],
          zoom: [0, zoom[1]],
        },
        dendro_tree_cols: {
          target: [pan[0], viz_state.viz.mat_height / 2],
          zoom: [zoom[0], 0],
        },
      });
    `;
    const code = `${shims}\n${source}\nmodule.exports = { redefine_global_view_state };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ redefine_global_view_state } = module.exports);
  });

  test('preserves both matrix pan axes when syncing the linked views', () => {
    const viz_state = {
      zoom: { ini_zoom_x: 0, ini_zoom_y: 0 },
      viz: {
        label_row_x: 15,
        label_col_y: 25,
        col_region: 60,
        dendrogram_width: 15,
        mat_width: 300,
        mat_height: 200,
      },
    };

    const view_state = redefine_global_view_state(
      viz_state,
      'rows',
      [2, 3],
      [111, 222]
    );

    expect(view_state.matrix.target).toEqual([111, 222]);
    expect(view_state.rows.target).toEqual([15, 222]);
    expect(view_state.cols.target).toEqual([111, 25]);
    expect(view_state.dendro_rows.target).toEqual([15, 222]);
    expect(view_state.dendro_cols.target).toEqual([111, 25]);
    expect(view_state.dendro_tree_rows).toEqual({
      target: [150, 222],
      zoom: [0, 3],
    });
    expect(view_state.dendro_tree_cols).toEqual({
      target: [111, 100],
      zoom: [2, 0],
    });
    expect(view_state.dendro_tree_static).toEqual({
      target: [150, 100],
      zoom: [0, 0],
    });
  });
});
