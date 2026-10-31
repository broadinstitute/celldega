/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../read_zarr/gene_signatures.js'), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const { make_gene_signatures_source } = new Function(
  'zarrita',
  `${source}\nreturn { make_gene_signatures_source };`
)({});
const nodes = () => ({
  '': { attrs: {} },
  obs: { attrs: { _index: 'types' } },
  var: { attrs: { _index: '_index' } },
  'obs/types': { data: ['T', 'B'] },
  'var/_index': { data: ['A', 'B'] },
  X: { shape: [2, 2], stride: [1, 2], data: new Float32Array([1, 3, 2, 4]) },
  'uns/viewport_signature': JSON.stringify({
    groupby: 'cell_type',
    units: 'mean counts',
  }),
});
const read = async (values) => {
  const requested = [];
  const open = async (location) => {
    if (!(location in values)) throw new Error(`Missing ${location}`);
    return values[location];
  };
  const zarr = {
    root: () => ({ resolve: (key) => key }),
    open: { v3: open, v2: open },
    get: async (node) => {
      requested.push(node);
      return node;
    },
  };
  // Opening the root passes its Location object, rather than a path.
  zarr.open.v3 = async (location) =>
    typeof location === 'object' ? values[''] : open(location);
  return {
    result: await make_gene_signatures_source(zarr)({ get: () => {} }),
    requested,
  };
};

test('reads dense AnnData signatures with nonstandard strides and explicit units', async () => {
  const { result } = await read(nodes());
  expect(result.groupby).toBe('cell_type');
  expect(result.units).toBe('mean counts');
  expect(result.genes).toEqual(['A', 'B']);
  expect(Array.from(result.means.get('T'))).toEqual([1, 2]);
  expect(Array.from(result.means.get('B'))).toEqual([3, 4]);
});

test.each([
  { X: { shape: [2, 2], data: [-1, 1, 2, 3] } },
  { X: { shape: [2, 2], data: [NaN, 1, 2, 3] } },
  { X: { attrs: { 'encoding-type': 'csr_matrix' } } },
  { 'obs/types': { data: ['T', 'T'] } },
  { 'uns/viewport_signature': JSON.stringify({ groupby: 'cell_type' }) },
])('rejects invalid or z-scored signature stores (%s)', async (override) => {
  await expect(read({ ...nodes(), ...override })).rejects.toThrow(
    /signatures/i
  );
});
