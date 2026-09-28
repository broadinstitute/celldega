/* global require */
const fs = require('fs');
const path = require('path');
const d3 = {};
new Function('exports', 'module', fs.readFileSync(path.join(path.dirname(require.resolve('d3')), '../dist/d3.js'), 'utf8'))(d3, { exports: d3 });

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export (const|function) /gm, '$1 ');
const api = new Function(
  'interpolateViridis',
  `${read('utils/compact_data.js')}\n${read('utils/hexToRgb.js')}\n${read('global_variables/cell_attributes.js')}\n${read('global_variables/cat.js')}\n${read('deck-gl/layers/cell_color.js')}\n${read('deck-gl/layers/path_layer.js')}\nreturn { apply_cell_attribute, numeric_attribute_color, select_category, get_cell_color, get_path_color };`
)(d3.interpolateViridis);

const fixture = () => ({
  cats: {
    inst_cell_attr: 'leiden',
    meta_cell_attr: ['leiden', 'counts', 'cell_type'],
    meta_cell: { a: ['0', 0, 'T'], b: ['1', null, 'B'], c: ['1', 10, 'T'] },
    cell_names_array: ['a', 'b', 'c'],
    color_dict_cluster: { 0: [255, 0, 0], 1: [0, 255, 0] },
    selected_cats: [],
    polygon_cell_names: ['a', 'b', 'c'],
  },
  model: {
    get: (name) =>
      name === 'cell_attribute_types'
        ? { counts: 'numeric', leiden: 'categorical', cell_type: 'categorical' }
        : {},
  },
  combo_data: {},
  spatial: {
    cell_scatter_data: {
      attributes: { getPosition: { value: [0, 0, 2, 2, 4, 4], size: 2 } },
    },
  },
});

test('numeric obs colors keep zero visible and missing values gray in points and polygons', () => {
  const state = fixture();
  api.apply_cell_attribute(state, 'counts');
  expect(state.cats.numeric_domain).toEqual([0, 10]);
  expect(state.cats.numeric_missing).toBe(1);
  expect(api.get_cell_color(state.cats, new Set(), null, { index: 0 })).toEqual(
    [68, 1, 84, 255]
  );
  expect(api.get_cell_color(state.cats, new Set(), null, { index: 1 })).toEqual(
    [156, 163, 175, 255]
  );
  expect(api.get_path_color(state.cats, null, { index: 2 })).toEqual([
    253, 231, 37, 255,
  ]);
  expect(state.combo_data.cell_compact.categoryNames).toEqual([]);
});

test('switching back from numeric restores categorical palette and viewport-count categories', () => {
  const state = fixture();
  const palette = state.cats.color_dict_cluster;
  api.apply_cell_attribute(state, 'counts');
  api.apply_cell_attribute(state, 'leiden');
  expect(state.cats.color_dict_cluster).toBe(palette);
  expect(palette).toEqual({ 0: [255, 0, 0], 1: [0, 255, 0] });
  expect(state.cats.cluster_counts).toEqual([
    { name: '1', value: 2 },
    { name: '0', value: 1 },
  ]);
  expect([...state.combo_data.cell_compact.categoryIds]).toEqual([0, 1, 1]);
  expect(state.combo_data.cell_compact.positions).toEqual([0, 0, 2, 2, 4, 4]);
});

test('Shift-click adds/removes categories without replacing the other selected groups', () => {
  const cats = { selected_cats: [] };
  const store = { selected_cats: { set: jest.fn() } };
  api.select_category(cats, '0', store);
  api.select_category(cats, '1', store, true);
  expect(cats.selected_cats).toEqual(['0', '1']);
  api.select_category(cats, '0', store, true);
  expect(cats.selected_cats).toEqual(['1']);
  api.select_category(cats, '1', store);
  expect(cats.selected_cats).toEqual([]);
});

test('gene expression mode takes precedence over active numeric obs coloring', () => {
  const state = fixture();
  api.apply_cell_attribute(state, 'counts');
  state.cats.cat = 'INS';
  state.cats.cell_exp_array = [0, 100, 255];
  expect(api.get_cell_color(state.cats, new Set(), null, { index: 0 })).toEqual(
    [0, 0, 0, 0]
  );
  expect(api.get_cell_color(state.cats, new Set(), null, { index: 1 })).toEqual(
    [255, 0, 0, 100]
  );
});

test('Parquet obs decoding preserves Arrow numeric validity rather than coercing missing to zero', async () => {
  const { TextEncoder, TextDecoder } = require('util');
  global.TextEncoder = TextEncoder;
  global.TextDecoder = TextDecoder;
  const arrow = require('apache-arrow');
  const table = arrow.tableFromArrays({
    cell_id: ['a', 'b', 'c'],
    counts: [0, null, 10],
  });
  const decode = new Function(
    'arrayBufferToArrowTable',
    `${read('read_parquet/table_accessors.js')}\n${read('read_parquet/objects_from_parquet.js')}\nreturn objects_from_parquet;`
  )(async () => table);
  const result = await decode(new Uint8Array([1]), 'cell_id');
  expect(result.result).toEqual({ a: [0], b: [null], c: [10] });
});
