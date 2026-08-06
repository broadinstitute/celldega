/* global require */

describe('cell color selection semantics', () => {
  let get_cell_color;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/layers/cell_color.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { get_cell_color };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_cell_color } = module.exports);
  });

  const makeCats = (overrides = {}) => ({
    cat: 'cluster',
    cell_names_array: ['cell-a', 'cell-b', 'cell-c'],
    cell_cats: ['A', 'B', 'A'],
    selected_cats: [],
    color_dict_cluster: {
      A: [10, 20, 30],
      B: [40, 50, 60],
    },
    cell_exp_array: [0, 128, 255],
    ...overrides,
  });

  test('cluster mode hides cells outside selected clusters', () => {
    const cats = makeCats({ selected_cats: ['A'] });

    expect(get_cell_color(cats, new Set(), null, { index: 0 })).toEqual([
      10, 20, 30, 255,
    ]);
    expect(get_cell_color(cats, new Set(), null, { index: 1 })).toEqual([
      0, 0, 0, 0,
    ]);
  });

  test('gene mode leaves zero-expression cells transparent', () => {
    const cats = makeCats({ cat: 'GeneA', selected_cats: ['GeneA'] });

    expect(get_cell_color(cats, new Set(), null, { index: 0 })).toEqual([
      0, 0, 0, 0,
    ]);
    expect(get_cell_color(cats, new Set(), null, { index: 1 })).toEqual([
      255, 0, 0, 128,
    ]);
  });

  test('gene mode applies selected cluster filters when present', () => {
    const cats = makeCats({ cat: 'GeneA', selected_cats: ['A'] });

    expect(get_cell_color(cats, new Set(), null, { index: 1 })).toEqual([
      0, 0, 0, 0,
    ]);
    expect(get_cell_color(cats, new Set(), null, { index: 2 })).toEqual([
      255, 0, 0, 255,
    ]);
  });
});
