/* global require */

const fs = require('fs');
const path = require('path');

const load = (file, names, prelude = '') => {
  const source = fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export (const |function )/gm, '$1');
  return new Function(`${prelude}\n${source}\nreturn { ${names} };`)();
};

// zarrita is ESM-only; the module's default reader is never called here.
const { make_anndata_zarr_source, fallback_colors, fetch_with_retry } = load(
  '../read_zarr/anndata_zarr.js',
  'make_anndata_zarr_source, fallback_colors, fetch_with_retry',
  'const zarrita = {};'
);

const row_major = (shape) =>
  shape.map((_, i) => shape.slice(i + 1).reduce((a, b) => a * b, 1));

// An in-memory stand-in for zarrita. Like zarrita without `kind`, opening a
// path returns whichever node is there; arrays carry a shape, groups do not.
const fake_zarr = (nodes, requested = []) => ({
  root: () => ({ resolve: (p) => p }),
  open: {
    v3: async (p) => {
      if (!(p in nodes)) throw new Error(`missing ${p}`);
      return { attrs: {}, ...nodes[p] };
    },
    v2: async () => {
      throw new Error('v2 not available');
    },
  },
  slice: (start, stop) => ({ start, stop }),
  get: async ({ data, shape }, selection) => {
    if (!selection) return { data, shape, stride: row_major(shape) };
    const [{ start, stop }] = selection;
    requested.push([start, stop]);
    return {
      data: data.slice(start, stop),
      shape: [stop - start],
      stride: [1],
    };
  },
});

const array = (data, shape = [data.length]) => ({ data, shape });
const csc = (shape) => ({
  attrs: { 'encoding-type': 'csc_matrix', shape },
});

// Four cells by three genes. Counts (cells x genes):
//   c0: G0=1        c1: G0=3, G2=5        c2: (none)        c3: G2=2
const store_nodes = ({ var_columns = ['mean', 'max'], ...overrides } = {}) => ({
  obs: { attrs: { _index: '_index', 'column-order': ['leiden', 'batch'] } },
  'obs/_index': array(['c0', 'c1', 'c2', 'c3']),
  'obs/leiden': { attrs: { 'encoding-type': 'categorical' } },
  // 'unused' has no cells; it still gets a color and a count of 0.
  'obs/leiden/categories': array(['B', 'T', 'unused']),
  'obs/leiden/codes': array(Int8Array.from([1, 0, 1, -1])),
  'obs/batch': array(['b1', 'b1', 'b2', 'b2']),
  var: { attrs: { _index: '_index', 'column-order': var_columns } },
  'var/_index': array(['G0', 'G1', 'G2']),
  'var/mean': array(Float64Array.from([1, 0, 1.75])),
  'var/max': array(Float32Array.from([3, 0, 5])),
  X: { attrs: { 'encoding-type': 'csr_matrix', shape: [4, 3] } },
  'layers/counts_csc': csc([4, 3]),
  'layers/counts_csc/indptr': array(BigInt64Array.from([0n, 2n, 2n, 4n])),
  'layers/counts_csc/indices': array(Int32Array.from([0, 1, 1, 3])),
  'layers/counts_csc/data': array(Float32Array.from([1, 3, 5, 2])),
  'uns/leiden_colors': array(['#111111', '#222222', '#333333']),
  // Stored (n_cells, 2) with column-major strides.
  'obsm/X_umap': {
    data: Float64Array.from([0, 1, 2, 3, 10, 11, 12, 13]),
    shape: [4, 2],
    stride: [1, 4],
  },
  ...overrides,
});

// A store whose metadata is consolidated lists its nodes.
const listed = (nodes) => ({
  get: async () => undefined,
  contents: () =>
    Object.keys(nodes).map((p) => ({
      path: `/${p}`,
      kind: nodes[p].shape ? 'array' : 'group',
    })),
});
const unlisted = { get: async () => undefined };

const open = (nodes, options = {}, store = listed(nodes), requested = []) => {
  const zarr = fake_zarr(nodes, requested);
  // The umap node needs its own strides, so `get` passes them through.
  const { get } = zarr;
  zarr.get = async (node, selection) =>
    node.stride && !selection
      ? { data: node.data, shape: node.shape, stride: node.stride }
      : get(node, selection);
  return make_anndata_zarr_source(zarr)(store, {
    cell_attr: ['leiden', 'batch'],
    cluster_attr: 'leiden',
    ...options,
  });
};

describe('anndata_zarr_source', () => {
  it('reads cells, genes, metadata, and the UMAP from the store', async () => {
    const source = await open(store_nodes());

    expect(source.matrix_path).toBe('layers/counts_csc');
    expect(source.cell_names).toEqual(['c0', 'c1', 'c2', 'c3']);
    expect(source.gene_names).toEqual(['G0', 'G1', 'G2']);
    expect(source.gene_mean).toEqual([1, 0, 1.75]);
    expect(source.gene_max).toEqual([3, 0, 5]);
    expect(source.gene_colors).toEqual(fallback_colors(3));
    expect(source.landscape_parameters).toMatchObject({
      technology: 'Chromium',
      use_int_index: true,
    });

    expect(source.meta_cell).toEqual({
      result: {
        c0: ['T', 'b1'],
        c1: ['B', 'b1'],
        c2: ['T', 'b2'],
        c3: ['nan', 'b2'],
      },
      attr: ['leiden', 'batch'],
    });
    expect(source.meta_cluster).toEqual({
      result: {
        B: ['#111111', 1],
        T: ['#222222', 2],
        unused: ['#333333', 0],
      },
      attr: ['color', 'count'],
    });
    expect(source.umap).toEqual({
      c0: [0, 10],
      c1: [1, 11],
      c2: [2, 12],
      c3: [3, 13],
    });
  });

  it('reads one gene as a slice between its indptr entries', async () => {
    const requested = [];
    const nodes = store_nodes();
    const { cbg_reader } = await open(nodes, {}, listed(nodes), requested);

    const g2 = await cbg_reader.readGeneExpression('G2');
    expect(Array.from(g2.cell_names)).toEqual([1, 3]);
    expect(Array.from(g2.cell_exp)).toEqual([5, 2]);
    expect(requested).toEqual([
      [2, 4],
      [2, 4],
    ]);

    // No expressing cells, or a gene the store doesn't have: nothing to fetch.
    const empty = await Promise.all(
      ['G1', 'NOPE'].map((gene) => cbg_reader.readGeneExpression(gene))
    );
    empty.forEach(({ cell_names }) => expect(cell_names).toHaveLength(0));
    expect(requested).toHaveLength(2);
  });

  it('falls back to detection rates, generated colors, and sorted clusters', async () => {
    const nodes = store_nodes({ var_columns: [] });
    delete nodes['uns/leiden_colors'];
    delete nodes['obsm/X_umap'];
    nodes['obs/leiden'] = array(['T', 'B', 'T', 'B']);
    const source = await open(nodes);

    // Fraction of the 4 cells with a stored value, from indptr alone.
    expect(source.gene_mean).toEqual([0.5, 0, 0.5]);
    expect(source.gene_max).toBeNull();
    expect(source.umap).toBeNull();
    expect(source.meta_cluster.result).toEqual({
      B: [fallback_colors(2)[0], 2],
      T: [fallback_colors(2)[1], 2],
    });
  });

  it('uses X when it is CSC, or the layer named in zarr_layer', async () => {
    const x_nodes = store_nodes({
      X: csc([4, 3]),
      'X/indptr': array(Int32Array.from([0, 1, 1, 1])),
      'X/indices': array(Int32Array.from([2])),
      'X/data': array(Float32Array.from([7])),
    });
    const from_x = await open(x_nodes, {}, unlisted);
    expect(from_x.matrix_path).toBe('X');
    expect(
      Array.from((await from_x.cbg_reader.readGeneExpression('G0')).cell_exp)
    ).toEqual([7]);

    const named = await open(store_nodes(), { layer: 'counts_csc' }, unlisted);
    expect(named.matrix_path).toBe('layers/counts_csc');
  });

  it('explains how to provide a CSC matrix', async () => {
    // Unconsolidated: the layers can't be listed.
    await expect(open(store_nodes(), {}, unlisted)).rejects.toThrow(
      /pass zarr_layer.*consolidate/
    );

    const no_csc = store_nodes();
    for (const key of Object.keys(no_csc)) {
      if (key.startsWith('layers/')) delete no_csc[key];
    }
    await expect(open(no_csc)).rejects.toThrow(/no CSC layer.*tocsc\(\)/);

    const two = store_nodes({ 'layers/raw_csc': csc([4, 3]) });
    await expect(open(two)).rejects.toThrow(
      /several CSC layers \(counts_csc, raw_csc\)/
    );

    await expect(open(store_nodes(), { layer: 'X' })).rejects.toThrow(
      /X in .* is csr_matrix; Landscape needs a CSC copy/
    );
    await expect(open(store_nodes(), { layer: 'missing' })).rejects.toThrow(
      /has no layers\/missing/
    );

    const mismatched = store_nodes({ 'layers/counts_csc': csc([5, 3]) });
    await expect(open(mismatched)).rejects.toThrow(
      /5 x 3, but obs and var have 4 and 3/
    );
  });
});

describe('update_cell_exp_array with a Zarr reader', () => {
  const { update_cell_exp_array } = load(
    '../global_variables/cell_exp_array.js',
    'update_cell_exp_array',
    `const options = { fetch: {} };
     const get_arrow_table = async () => { throw new Error('no DegaFiles'); };
     const getGeneExpressionColumns = () => { throw new Error('no DegaFiles'); };`
  );
  const reader = {
    readGeneExpression: async (gene) =>
      gene === 'G2'
        ? {
            cell_names: Int32Array.from([1, 3]),
            cell_exp: Float64Array.from([5, 2]),
          }
        : { cell_names: new Int32Array(), cell_exp: new Float64Array() },
  };
  const cats = () => ({
    cell_names_array: ['c0', 'c1', 'c2', 'c3'],
    nameMapping_inv: ['c0', 'c1', 'c2', 'c3'],
    cell_exp_array: new Uint8Array(4),
    meta_cell_id_set: null,
  });

  it('uses integer cell indices and the stored max', async () => {
    const state = cats();
    await update_cell_exp_array(
      state,
      { meta_gene: { G2: { max: 10 } } },
      '',
      'G2',
      'default',
      true,
      null,
      reader
    );
    expect(state.cell_exp_max).toBe(10);
    expect(Array.from(state.cell_exp_raw)).toEqual([0, 5, 0, 2]);
  });

  it('computes the max from the loaded values when none is stored', async () => {
    const state = cats();
    await update_cell_exp_array(
      state,
      { meta_gene: { G2: { max: undefined } } },
      '',
      'G2',
      'default',
      true,
      null,
      reader
    );
    expect(state.cell_exp_max).toBe(5);
    expect(state.cell_exp_array[1]).toBe(255);
  });
});

describe('fetch_with_retry', () => {
  // jsdom has no Request; the retry only needs to pass something through.
  global.Request ??= class {
    constructor(url) {
      this.url = url;
    }
  };
  const respond = (status) => ({ status });
  const run = (outcomes) => {
    const fetch_fn = jest.fn(async () => {
      const next = outcomes.shift();
      if (next instanceof Error) throw next;
      return respond(next);
    });
    return { fetch_fn, options: { delay_ms: 0, fetch_fn } };
  };

  it('retries dropped connections and server errors', async () => {
    const { fetch_fn, options } = run([
      new TypeError('fetch failed'),
      503,
      200,
    ]);
    const response = await fetch_with_retry('chunk', {}, options);
    expect(response.status).toBe(200);
    expect(fetch_fn).toHaveBeenCalledTimes(3);
  });

  it('returns 404s at once and gives up after the last attempt', async () => {
    const missing = run([404]);
    expect((await fetch_with_retry('chunk', {}, missing.options)).status).toBe(
      404
    );
    expect(missing.fetch_fn).toHaveBeenCalledTimes(1);

    const down = run([
      new TypeError('a'),
      new TypeError('b'),
      new TypeError('c'),
    ]);
    await expect(fetch_with_retry('chunk', {}, down.options)).rejects.toThrow(
      'c'
    );
    expect(down.fetch_fn).toHaveBeenCalledTimes(3);
  });
});
