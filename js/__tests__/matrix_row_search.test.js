/* global require */

describe('Clustergram row search', () => {
  let find_matrix_row_index;
  let get_row_search_zoom;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');
    const strip_modules = (source) =>
      source
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const gene_search_source = strip_modules(
      fs.readFileSync(path.join(__dirname, '../ui/gene_search.js'), 'utf8')
    );
    const row_search_source = strip_modules(
      fs.readFileSync(
        path.join(__dirname, '../deck-gl/matrix/row_search.js'),
        'utf8'
      )
    );
    const shims = `
      const set_gene_search_input = () => {};
      const get_axis_display_count = (viz_state, axis) =>
        axis === 'row' ? viz_state.mat.num_rows : viz_state.mat.num_cols;
    `;
    const code = `${shims}\n${gene_search_source}\n${row_search_source}\nmodule.exports = { find_matrix_row_index, get_row_search_zoom };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ find_matrix_row_index, get_row_search_zoom } = module.exports);
  });

  test('finds canonical and display row names without case sensitivity', () => {
    const viz_state = {
      row_nodes: [{ name: 'EPHA7' }, { name: 'FAM124A' }],
      labels: {
        row_label_data: [
          { display_name: 'EPHA7' },
          { display_name: 'Family 124A' },
        ],
      },
    };

    expect(find_matrix_row_index(viz_state, 'epha7')).toBe(0);
    expect(find_matrix_row_index(viz_state, 'family 124a')).toBe(1);
    expect(find_matrix_row_index(viz_state, 'missing')).toBeNull();
  });

  test('magnifies only a vertically accordion-shaped matrix', () => {
    const vertical = {
      mat: { num_rows: 1_200, num_cols: 12, viz_mode: 'heatmap' },
      zoom: { ini_zoom_x: 0, zoom_delay: Math.log2(100) },
    };
    const [zoom_x, zoom_y] = get_row_search_zoom(vertical, [0, 0]);

    expect(zoom_y).toBeGreaterThan(5);
    expect(zoom_x).toBe(0);

    const wide = {
      mat: { num_rows: 12, num_cols: 30, viz_mode: 'heatmap' },
      zoom: { ini_zoom_x: 0, zoom_delay: 0 },
    };
    expect(get_row_search_zoom(wide, [1, 2])).toEqual([1, 2]);
  });
});
