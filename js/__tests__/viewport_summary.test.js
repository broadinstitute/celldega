/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const source = jest.fn();
const publish_selection = jest.fn();
const { viewport_cells, estimate_viewport_genes, initialize_viewport_summary } =
  new Function(
    'gene_signatures_source',
    'areBarDataEqual',
    'publish_selected_cells',
    `${read('umap/viewport_summary.js')}\nreturn { viewport_cells, estimate_viewport_genes, initialize_viewport_summary };`
  )(
    source,
    (a, b) => JSON.stringify(a) === JSON.stringify(b),
    publish_selection
  );
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

test('uses UMAP and XY positions, refreshes after load, exports all IDs, and restores spatial bars', async () => {
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
  const viz = {
    containers,
    cats: {
      cell_names_array: ['a', 'b', 'c'],
      cell_cats: ['T', 'B', 'T'],
      inst_cell_attr: 'cell_type',
      cluster_counts: [{ name: 'T', value: 100 }],
    },
    genes: { top_gene_counts: [{ name: 'global', value: 1 }] },
    model: { get: () => 'signatures.zarr', set: jest.fn() },
    spatial: {
      cell_umap_scatter_positions: new Float64Array([0, 0, 1, 1, 2, 2]),
      cell_xy_scatter_positions: new Float64Array([5, 5, 1, 1, 6, 6]),
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
  expect(parent.textContent).toContain('Loading gene signatures');
  resolve(signatures);
  await Promise.resolve();
  expect(viz.obs_store.new_gene_bar_data.get()[0]).toEqual({
    name: 'B',
    value: 2,
  });
  parent.querySelector('button').click();
  expect(publish_selection).toHaveBeenLastCalledWith(viz, ['a', 'b', 'c']);
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
  expect(viz.obs_store.new_gene_bar_data.get()).toEqual([]);
  expect(parent.textContent).toContain('require cell_type');
  viz.obs_store.landscape_view.set('spatial');
  viz.refresh_viewport();
  expect(viz.obs_store.new_gene_bar_data.get()).toEqual(
    viz.genes.top_gene_counts
  );
  expect(parent.querySelector('button').hidden).toBe(true);
  dispose();
  expect(parent.children).toHaveLength(2);
  expect(viz.update_embedding_viewport).toBeUndefined();
});
