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

    const code = `${source}\nmodule.exports = { redefine_global_view_state };`;
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
  });
});
