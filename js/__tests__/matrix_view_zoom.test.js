/* global require */

describe('matrix edge zoom targets', () => {
  let get_matrix_edge_zoom_target;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/on_view_state_change.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const code = `${source}\nmodule.exports = { get_matrix_edge_zoom_target };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_matrix_edge_zoom_target } = module.exports);
  });

  test.each([
    ['column labels', 'cols', [40, 25], [40, Number.NEGATIVE_INFINITY]],
    [
      'column dendrogram',
      'dendro_cols',
      [40, 25],
      [40, Number.POSITIVE_INFINITY],
    ],
    ['row labels', 'rows', [15, 70], [Number.NEGATIVE_INFINITY, 70]],
    ['row dendrogram', 'dendro_rows', [15, 70], [Number.POSITIVE_INFINITY, 70]],
    ['matrix body', 'matrix', [40, 70], [40, 70]],
  ])('uses the matching edge for %s', (_name, viewId, target, expected) => {
    expect(get_matrix_edge_zoom_target(viewId, target)).toEqual(expected);
  });
});
