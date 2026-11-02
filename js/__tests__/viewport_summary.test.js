/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const source = jest.fn();
const load_gene = jest.fn();
const from_parquet = jest.fn();
const fetch_table = jest.fn();
const { viewport_cells, estimate_viewport_genes, initialize_viewport_summary } =
  new Function(
    'gene_signatures_source',
    'gene_signatures_from_parquet',
    'gene_signatures_from_table',
    'get_arrow_table',
    'options',
    'load_gene_expression',
    'areBarDataEqual',
    `${read('umap/viewport_summary.js')}\nreturn { viewport_cells, estimate_viewport_genes, initialize_viewport_summary };`
  )(
    source,
    from_parquet,
    (table, defaults) => ({ ...defaults, ...table }),
    fetch_table,
    { fetch: {} },
    load_gene,
    (a, b) => JSON.stringify(a) === JSON.stringify(b)
  );
// A d3 selection's style/attr getters and setters, for the TRX button.
const fake_button = () => {
  const styles = { color: 'gray', opacity: '1', cursor: 'pointer' };
  const attrs = { title: 'Transcripts' };
  const button = {
    styles,
    attrs,
    style: (key, value) => {
      if (value === undefined) return styles[key];
      styles[key] = value;
      return button;
    },
    attr: (key, value) => {
      if (value === undefined) return attrs[key];
      attrs[key] = value;
      return button;
    },
  };
  return button;
};
const observable = (initial) => {
  let value = initial;
  return {
    get: () => value,
    set: jest.fn((next) => {
      value = next;
    }),
  };
};
const signatures = {
  groupby: 'cell_type',
  units: 'mean log1p counts per 10,000',
  genes: ['A', 'B', 'zero'],
  means: new Map([
    ['T', new Float32Array([2, 0, 0])],
    ['B', new Float32Array([0, 6, 0])],
  ]),
};

test('counts finite cells inside the viewport, including its edges', () => {
  const result = viewport_cells(
    new Float64Array([0, 0, 1, 1, 2, 2, NaN, 0, 5, 5]),
    {
      cell_names_array: ['a', 'b', 'c', 'd', 'e'],
      cell_cats: ['T', 'B', 'T', 'B', null],
    },
    { min_x: 0, max_x: 2, min_y: 0, max_y: 2 }
  );
  expect(result).toEqual({
    indices: [0, 1, 2],
    all: false,
    bars: [
      { name: 'T', value: 2 },
      { name: 'B', value: 1 },
    ],
  });
  expect(estimate_viewport_genes(signatures, result.bars)).toEqual({
    covered: 3,
    bars: [
      { name: 'B', value: 2 },
      { name: 'A', value: 4 / 3 },
    ],
  });
  expect(estimate_viewport_genes(signatures, [])).toEqual({
    covered: 0,
    bars: [],
  });
  expect(
    estimate_viewport_genes(signatures, result.bars, new Set(['A'])).bars
  ).toEqual([{ name: 'A', value: 4 / 3 }]);
});

test('uses UMAP and XY positions, refreshes after load, and restores spatial bars', async () => {
  const parent = document.createElement('div');
  const containers = {
    bar_cluster: document.createElement('div'),
    bar_gene: document.createElement('div'),
  };
  parent.append(containers.bar_cluster, containers.bar_gene);
  let resolve;
  source.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    })
  );
  const trx = fake_button();
  const viz = {
    containers,
    buttons: { buttons: { trx } },
    cats: {
      cell_names_array: ['a', 'b', 'c', 'd'],
      cell_cats: ['T', 'B', 'T', 'B'],
      inst_cell_attr: 'cell_type',
      cluster_counts: [{ name: 'T', value: 100 }],
    },
    genes: { top_gene_counts: [{ name: 'global', value: 1 }] },
    model: { get: () => 'signatures.zarr', set: jest.fn() },
    // Cell d is out of view, so the gene bars are estimated.
    spatial: {
      cell_umap_scatter_positions: new Float64Array([0, 0, 1, 1, 2, 2, 5, 5]),
      cell_xy_scatter_positions: new Float64Array([5, 5, 1, 1, 6, 6, 7, 7]),
    },
    obs_store: {
      landscape_view: observable('umap'),
      new_cell_bar_data: observable([]),
      new_gene_bar_data: observable([]),
    },
  };
  const bounds = { min_x: 0, max_x: 2, min_y: 0, max_y: 2 };
  viz.refresh_viewport = () => viz.update_embedding_viewport(bounds);
  const dispose = initialize_viewport_summary(viz);
  viz.refresh_viewport();
  expect(viz.obs_store.new_cell_bar_data.get()).toEqual([
    { name: 'T', value: 2 },
    { name: 'B', value: 1 },
  ]);
  expect(trx.attrs.title).toContain('Loading gene signatures');
  // No captions: the bars and TRX carry it.
  expect(parent.textContent).toBe('');
  resolve(signatures);
  await Promise.resolve();
  expect(viz.obs_store.new_gene_bar_data.get()[0]).toEqual({
    name: 'B',
    value: 2,
  });
  viz.obs_store.landscape_view.set('xy');
  viz.refresh_viewport();
  expect(viz.obs_store.new_cell_bar_data.get()).toEqual([
    { name: 'B', value: 1 },
  ]);
  expect(viz.obs_store.new_gene_bar_data.get()).toEqual([
    { name: 'B', value: 6 },
  ]);
  viz.cats.inst_cell_attr = 'organ';
  viz.refresh_viewport();
  // Signatures for another attribute leave the whole-dataset genes, TRX gray.
  expect(viz.obs_store.new_gene_bar_data.get()).toEqual(
    viz.genes.top_gene_counts
  );
  expect(trx.styles.color).toBe('gray');
  expect(trx.attrs.title).toContain('require cell_type');
  viz.obs_store.landscape_view.set('spatial');
  viz.refresh_viewport();
  expect(viz.obs_store.new_gene_bar_data.get()).toEqual(
    viz.genes.top_gene_counts
  );
  expect(parent.querySelector('button')).toBeNull();
  dispose();
  expect(parent.children).toHaveLength(2);
  expect(viz.update_embedding_viewport).toBeUndefined();
});

const trx_viz = (overrides = {}) => {
  const parent = document.createElement('div');
  const containers = {
    bar_cluster: document.createElement('div'),
    bar_gene: document.createElement('div'),
  };
  parent.append(containers.bar_cluster, containers.bar_gene);
  const model_values = { gene_signature_url: 'signatures.zarr' };
  const viz = {
    parent,
    containers,
    cats: {
      cell_names_array: ['a', 'b', 'c'],
      cell_cats: ['T', 'B', 'T'],
      inst_cell_attr: 'cell_type',
      cluster_counts: [{ name: 'T', value: 2 }],
    },
    genes: { top_gene_counts: [{ name: 'global', value: 1 }] },
    model: { get: (key) => model_values[key], set: jest.fn() },
    spatial: {
      cell_umap_scatter_positions: new Float64Array([0, 0, 1, 1, 9, 9]),
    },
    vector_name_integer: true,
    global_base_url: 'http://data',
    seg: { version: 'default' },
    buttons: { buttons: { trx: fake_button() } },
    obs_store: {
      landscape_view: observable('umap'),
      new_cell_bar_data: observable([]),
      new_gene_bar_data: observable([]),
    },
    ...overrides,
  };
  return viz;
};

test('TRX is blue with every cell in view, purple for estimates, and stays estimated when panning', async () => {
  source.mockReturnValueOnce(Promise.resolve(signatures));
  const viz = trx_viz();
  const { trx } = viz.buttons.buttons;
  let bounds = { min_x: -1, max_x: 10, min_y: -1, max_y: 10 };
  viz.refresh_viewport = () => viz.update_embedding_viewport(bounds);
  const dispose = initialize_viewport_summary(viz);
  await Promise.resolve();
  viz.refresh_viewport();
  expect(viz.obs_store.new_gene_bar_data.get()).toEqual(
    viz.genes.top_gene_counts
  );
  expect(trx.styles.color).toBe('blue');
  bounds = { min_x: -1, max_x: 2, min_y: -1, max_y: 2 };
  viz.refresh_viewport();
  expect(trx.styles.color).toBe('purple');
  expect(viz.obs_store.new_gene_bar_data.get()[0]).toEqual({
    name: 'B',
    value: 3,
  });

  expect(viz.compute_embedding_viewport_exact).toBeUndefined();
  expect(load_gene).not.toHaveBeenCalled();
  expect(trx.attrs.title).not.toContain('Click');

  // Panning returns to the estimate.
  bounds = { min_x: -1, max_x: 1.5, min_y: -1, max_y: 1.5 };
  viz.refresh_viewport();
  expect(trx.styles.color).toBe('purple');
  viz.obs_store.landscape_view.set('spatial');
  viz.refresh_viewport();
  expect(trx.styles.color).toBe('gray');
  expect(trx.styles.cursor).toBe('pointer');
  expect(trx.attrs.title).toBe('Transcripts');
  dispose();
});

test('adata_sig bytes and DegaFiles df_sig.parquet supply signatures', async () => {
  from_parquet.mockResolvedValueOnce(signatures);
  const bytes = new Uint8Array([1, 2, 3]);
  const with_bytes = trx_viz({
    model: {
      get: (key) =>
        ({ gene_signature_parquet: bytes, cluster_attr: 'cell_type' })[key],
      set: jest.fn(),
    },
  });
  with_bytes.refresh_viewport = () =>
    with_bytes.update_embedding_viewport({
      min_x: -1,
      max_x: 2,
      min_y: -1,
      max_y: 2,
    });
  initialize_viewport_summary(with_bytes)();
  expect(from_parquet).toHaveBeenCalledWith(bytes, {
    groupby: 'cell_type',
    units: 'mean expression per cell',
  });

  fetch_table.mockResolvedValueOnce({ genes: ['A'] });
  const spatial = trx_viz({
    img: { landscape_parameters: { technology: 'Xenium' } },
    model: { get: () => undefined, set: jest.fn() },
    seg: { version: 'cellpose' },
  });
  spatial.refresh_viewport = () => {};
  initialize_viewport_summary(spatial);
  expect(fetch_table).toHaveBeenCalledWith(
    'http://data/df_sig_cellpose.parquet',
    {},
    null
  );

  // A clustering from Python (meta_cell_parquet) has no DegaFiles signatures.
  fetch_table.mockClear();
  initialize_viewport_summary(
    trx_viz({
      img: { landscape_parameters: { technology: 'Xenium' } },
      model: {
        get: (key) =>
          key === 'meta_cell_parquet' ? new Uint8Array([1]) : undefined,
        set: jest.fn(),
      },
    })
  );
  expect(fetch_table).not.toHaveBeenCalled();
});
