/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../read_zarr/gene_signatures.js'), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const { make_gene_signatures_source, gene_signatures_from_table } =
  new Function(
    'zarrita',
    `${source}\nreturn { make_gene_signatures_source, gene_signatures_from_table };`
  )({});
// An Arrow table's schema fields, schema metadata, and columns.
const arrow_table = (columns, metadata) => ({
  schema: {
    fields: Object.keys(columns).map((name) => ({ name })),
    metadata: new Map(Object.entries(metadata ?? {})),
  },
  getChild: (name) => ({ toArray: () => columns[name] }),
});
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

test('reads adata_sig parquet tables with their metadata, and df_sig with defaults', () => {
  const parsed = gene_signatures_from_table(
    arrow_table(
      { gene: ['A', 'B'], T: new Float32Array([1, 2]), B: [0, 3] },
      {
        viewport_signature: JSON.stringify({
          groupby: 'leiden',
          units: 'mean counts per cell',
        }),
      }
    ),
    { groupby: 'cell_type', units: 'mean expression per cell' }
  );
  expect(parsed.groupby).toBe('leiden');
  expect(parsed.units).toBe('mean counts per cell');
  expect(parsed.genes).toEqual(['A', 'B']);
  expect(Array.from(parsed.means.get('B'))).toEqual([0, 3]);

  const df_sig = gene_signatures_from_table(
    arrow_table({ __index_level_0__: ['A'], 1: [0.5], 2: [0.25] }),
    { groupby: 'cluster', units: 'mean counts per cell' }
  );
  expect(df_sig.groupby).toBe('cluster');
  expect([...df_sig.means.keys()]).toEqual(['1', '2']);

  expect(() =>
    gene_signatures_from_table(arrow_table({ gene: ['A'], T: [-1] }), {
      groupby: 'cell_type',
      units: 'counts',
    })
  ).toThrow('nonnegative');
  expect(() =>
    gene_signatures_from_table(arrow_table({ gene: ['A'], T: [1] }))
  ).toThrow('groupby/units');
});

test('reads the counts layer of a two-layer store, or the layer its metadata names', async () => {
  const two_layers = (meta) => ({
    ...nodes(),
    X: undefined,
    'layers/counts': { shape: [2, 2], data: new Float32Array([1, 2, 3, 4]) },
    'layers/log1p': {
      shape: [2, 2],
      data: new Float32Array([0.5, 0.25, 0.75, 0.125]),
    },
    'uns/viewport_signature': JSON.stringify({
      groupby: 'cell_type',
      units: 'mean counts per cell',
      layers: {
        counts: 'mean counts per cell',
        log1p: 'mean log1p counts per 10,000',
      },
      ...meta,
    }),
  });
  const counts = (await read(two_layers({}))).result;
  expect(Array.from(counts.means.get('B'))).toEqual([3, 4]);
  expect(counts.units).toBe('mean counts per cell');
  const log1p = (await read(two_layers({ layer: 'log1p' }))).result;
  expect(Array.from(log1p.means.get('T'))).toEqual([0.5, 0.25]);
  expect(log1p.units).toBe('mean log1p counts per 10,000');
});
