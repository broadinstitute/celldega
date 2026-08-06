/* global require */

describe('get_path_color polygon visibility', () => {
  let get_path_color;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/layers/path_layer.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    // Faithful shim of the real is_cluster_color_mode (cell_color.js): cluster
    // mode is the default when cats.cat is unset or 'cluster'.
    const shim = `const is_cluster_color_mode = (cats) => !cats.cat || cats.cat === 'cluster';`;

    const code = `${shim}\n${source}\nmodule.exports = { get_path_color };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_path_color } = module.exports);
  });

  const makeCats = (overrides = {}) => ({
    polygon_cell_names: ['cellA', 'cellB', 'cellC'],
    dict_cell_cats: { cellA: '0', cellB: '1', cellC: '2' },
    color_dict_cluster: {
      0: [10, 10, 10],
      1: [20, 20, 20],
      2: [30, 30, 30],
    },
    cat: 'cluster',
    selected_cats: [],
    ...overrides,
  });

  const alphaFor = (cats, index) => get_path_color(cats, index, { index })[3];

  it('shows every polygon in cluster mode with no selection', () => {
    const cats = makeCats();
    expect(alphaFor(cats, 0)).toBe(255);
    expect(alphaFor(cats, 1)).toBe(255);
    expect(alphaFor(cats, 2)).toBe(255);
  });

  it('filters to the selected cluster in cluster mode', () => {
    const cats = makeCats({ cat: 'cluster', selected_cats: ['1'] });
    expect(alphaFor(cats, 0)).toBe(0); // cluster 0
    expect(alphaFor(cats, 1)).toBe(255); // cluster 1 (selected)
    expect(alphaFor(cats, 2)).toBe(0); // cluster 2
  });

  it('keeps ALL polygons visible when a gene is selected (regression)', () => {
    // The bug: selecting a gene force-set selected_cats to the gene name, and
    // get_path_color filtered every polygon out (alpha 0) because no cluster
    // category matched the gene name -- so all cell boundaries vanished.
    const cats = makeCats({ cat: 'GAPDH', selected_cats: ['GAPDH'] });
    expect(alphaFor(cats, 0)).toBe(255);
    expect(alphaFor(cats, 1)).toBe(255);
    expect(alphaFor(cats, 2)).toBe(255);
  });

  it('still honors a real cluster filter while in gene mode', () => {
    // If a genuine cluster category is also present in gene mode, it should
    // still filter (mirrors the cell centroid layer's behavior).
    const cats = makeCats({ cat: 'GAPDH', selected_cats: ['GAPDH', '1'] });
    expect(alphaFor(cats, 0)).toBe(0);
    expect(alphaFor(cats, 1)).toBe(255); // cluster 1 kept
    expect(alphaFor(cats, 2)).toBe(0);
  });

  it('colors by cluster and falls back to blue for unknown categories', () => {
    const cats = makeCats();
    expect(get_path_color(cats, 1, { index: 1 })).toEqual([20, 20, 20, 255]);

    const unknown = makeCats({
      dict_cell_cats: { cellA: 'missing' },
      polygon_cell_names: ['cellA'],
    });
    // Unknown cluster -> default segmentation blue, still visible.
    expect(get_path_color(unknown, 0, { index: 0 })).toEqual([0, 0, 255, 255]);
  });
});
