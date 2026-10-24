/* global require */

describe('networkFromZarr', () => {
  let makeNetworkFromZarr;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../read_zarr/network_from_zarr.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    // zarrita is ESM-only; the module's default reader is never called here.
    ({ makeNetworkFromZarr } = new Function(
      `const zarrita = {};\n${source}\nreturn { makeNetworkFromZarr };`
    )());
  });

  const row_major = (shape) =>
    shape.map((_, i) => shape.slice(i + 1).reduce((a, b) => a * b, 1));

  // An in-memory stand-in for zarrita: node paths map to arrays or groups.
  const fake_zarr = (nodes) => ({
    root: () => ({ resolve: (path) => path }),
    open: {
      v3: async (path) => {
        if (!(path in nodes)) throw new Error(`missing ${path}`);
        return { shape: [], attrs: {}, ...nodes[path] };
      },
      v2: async () => {
        throw new Error('v2 not available');
      },
    },
    // Like zarrita, 0-d arrays come back as bare scalars.
    get: async ({ data, shape }) =>
      shape.length === 0 ? data : { data, shape, stride: row_major(shape) },
  });

  const array = (data, shape) => ({ data, shape });
  // The fake zarrita above reads node data directly; the store is a placeholder.
  const store = { get: async () => undefined };

  // Three rows (genes) by two columns (clusters), one view, and a size layer.
  const store_nodes = (meta_overrides = {}) => {
    const meta = {
      format: 'celldega.matrix',
      version: 1,
      row_entity: { entity: 'gene', attr: 'name' },
      col_entity: { entity: 'cell', attr: 'leiden' },
      row_attr: ['lineage'],
      col_attr: [],
      row_cats: ['lineage'],
      col_cats: [],
      has_size_matrix: true,
      viz: { name: 'demo', global_cat_colors: { 'T/NK': '#ff0000' } },
      views: [{ view_type: 'var', level: 2, level_unit: 'rows', n_rows: 2 }],
      ...meta_overrides,
    };
    const node_columns = (prefix, n, cats) => ({
      [prefix]: {
        attrs: { 'column-order': ['ini', 'clust', 'cat-0'] },
        shape: [n],
      },
      [`${prefix}/ini`]: array(
        BigInt64Array.from({ length: n }, (_, i) => BigInt(n - i)),
        [n]
      ),
      [`${prefix}/clust`]: array(
        Int32Array.from({ length: n }, (_, i) => i),
        [n]
      ),
      [`${prefix}/cat-0`]: array(cats, [n]),
    });
    return {
      'uns/celldega/meta_json': array(JSON.stringify(meta), []),
      // X is (columns, rows): column c0 = [1, 2, 3], c1 = [4, NaN, 6].
      X: array(Float32Array.from([1, 2, 3, 4, NaN, 6]), [2, 3]),
      'layers/size': array(
        Float32Array.from([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
        [2, 3]
      ),
      var: { attrs: { _index: '_index' } },
      'var/_index': array(['g0', 'g1', 'g2'], [3]),
      obs: { attrs: { _index: '_index' } },
      'obs/_index': array(['c0', 'c1'], [2]),
      ...node_columns('varm/celldega_nodes', 3, ['T/NK', 'B', 'T/NK']),
      ...node_columns('obsm/celldega_nodes', 2, ['a', 'b']),
      'uns/celldega/linkage/row': array(
        Float64Array.from([0, 1, 0.5, 2, 2, 3, 0.9, 3]),
        [2, 4]
      ),
      'uns/celldega/linkage/col': array(
        Float64Array.from([0, 1, 0.7, 2]),
        [1, 4]
      ),
      'uns/celldega/views/row_indices': array(Int32Array.from([0, 2]), [2]),
      'uns/celldega/views/row_clust': array(Int32Array.from([1, 0, 2]), [1, 3]),
      'uns/celldega/views/col_clust': array(Int32Array.from([2, 1]), [1, 2]),
      'uns/celldega/views/row_linkage': array(
        Float64Array.from([0, 1, 0.4, 2]),
        [1, 4]
      ),
      'uns/celldega/views/col_linkage': array(
        Float64Array.from([0, 1, 0.6, 2]),
        [1, 1, 4]
      ),
    };
  };

  it('builds the network the matrix viz renders', async () => {
    const read = makeNetworkFromZarr(fake_zarr(store_nodes()));
    const network = await read(store);

    expect(network.mat).toEqual([
      [1, 4],
      [2, 0],
      [3, 6],
    ]);
    expect(network.size_mat[0][1]).toBeCloseTo(0.4);
    expect(network.row_nodes[0]).toEqual({
      name: 'g0',
      ini: 3,
      clust: 0,
      'cat-0': 'T/NK',
    });
    expect(network.col_nodes.map((node) => node.name)).toEqual(['c0', 'c1']);
    expect(network.linkage.row).toEqual([
      [0, 1, 0.5, 2],
      [2, 3, 0.9, 3],
    ]);
    expect(network.global_cat_colors).toEqual({ 'T/NK': '#ff0000' });
    expect(network.row_entity).toEqual({ entity: 'gene', attr: 'name' });
  });

  it('unpacks views into plain arrays', async () => {
    const read = makeNetworkFromZarr(fake_zarr(store_nodes()));
    const [view] = (await read(store)).views;

    expect(view).toMatchObject({
      view_type: 'var',
      level: 2,
      n_rows: 2,
      row_indices: [0, 2],
      row_clust: [1, 0, 2],
      col_clust: [2, 1],
      row_linkage: [[0, 1, 0.4, 2]],
      col_linkage: [[0, 1, 0.6, 2]],
    });
    ['row_indices', 'row_clust', 'col_clust', 'row_linkage'].forEach((key) => {
      expect(Array.isArray(view[key])).toBe(true);
    });
  });

  it('reads stores without views or a size matrix', async () => {
    const nodes = store_nodes({ views: [], has_size_matrix: false });
    // A one-column matrix has a zero-size column linkage.
    nodes['uns/celldega/linkage/col'] = array(new Float64Array(0), [0, 4]);
    const network = await makeNetworkFromZarr(fake_zarr(nodes))(store);

    expect(network.views).toEqual([]);
    expect(network.size_mat).toBeUndefined();
    expect(network.linkage.col).toEqual([]);
  });

  it('rejects stores from a newer format version', async () => {
    const read = makeNetworkFromZarr(fake_zarr(store_nodes({ version: 2 })));
    await expect(read(store)).rejects.toThrow('unsupported store');
  });
});
