/* global require */

describe('neighborhood-cloud cluster-selected cell centroid loading', () => {
  let refresh_nbhd_cloud_cluster_cells;
  const fetchedUrls = [];
  const cellsBox = { value: null };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = readStripped('../deck-gl/layers/nbhd_cloud_cell_layer.js');

    // Shims for the module's real imports -- get_arrow_table (network
    // fetch) and parse_cells_tables (arrow -> typed arrays) are stubbed so
    // this test exercises only the fetch/cache/filter/color logic that's
    // actually new here.
    const shims = `
      const options = { fetch: {} };
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_cells_tables = () => cellsBox.value;
      const getModelMatrixProps = () => ({});
    `;

    const code = `${shims}\n${source}\nmodule.exports = { refresh_nbhd_cloud_cluster_cells };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', 'cellsBox', code)(
      module,
      module.exports,
      fetchedUrls,
      cellsBox
    );
    ({ refresh_nbhd_cloud_cluster_cells } = module.exports);
  });

  beforeEach(() => {
    fetchedUrls.length = 0;
  });

  const makeViewState = (nbhd_cloud_overrides = {}) => ({
    nbhd_cloud: { ...nbhd_cloud_overrides },
    cats: { color_dict_cluster: { 1: [10, 20, 30] } },
    global_base_url: 'http://example.test',
    aws: null,
  });

  const makeLayersObj = () => ({
    nbhd_cloud_cell_layer: {
      clone(props) {
        return { ...this, ...props };
      },
    },
  });

  test('no cluster selected -> clears the layer without fetching', async () => {
    const viz_state = makeViewState({ selected_cluster_ids: new Set() });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]);
    expect(layers_obj.nbhd_cloud_cell_layer.data.length).toBe(0);
  });

  test('fetches by_cluster and applies the cluster color to every cell', async () => {
    cellsBox.value = {
      length: 2,
      positions: new Float32Array([1, 1, 1, 2, 2, 2]),
      clusterIds: ['1', '1'],
      sliceIds: ['s0', 's1'],
    };

    const viz_state = makeViewState({ selected_cluster_ids: new Set(['1']) });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/cells/by_cluster/cluster_1.parquet',
    ]);

    const { data } = layers_obj.nbhd_cloud_cell_layer;
    expect(data.length).toBe(2);
    expect(Array.from(data.attributes.getPosition.value)).toEqual([
      1, 1, 1, 2, 2, 2,
    ]);
    expect(Array.from(data.attributes.getColor.value)).toEqual([
      10, 20, 30, 255, 10, 20, 30, 255,
    ]);
  });

  test('an active slice selection narrows the cluster fetch to that slice, client-side', async () => {
    cellsBox.value = {
      length: 3,
      positions: new Float32Array([1, 1, 1, 2, 2, 2, 3, 3, 3]),
      clusterIds: ['1', '1', '1'],
      sliceIds: ['s0', 's1', 's0'],
    };

    const viz_state = makeViewState({
      selected_cluster_ids: new Set(['1']),
      selected_slice_ids: new Set(['s0']),
    });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

    const { data } = layers_obj.nbhd_cloud_cell_layer;
    expect(data.length).toBe(2);
    expect(Array.from(data.attributes.getPosition.value)).toEqual([
      1, 1, 1, 3, 3, 3,
    ]);
  });

  test('a second call for the same cluster reuses the cached fetch', async () => {
    cellsBox.value = {
      length: 1,
      positions: new Float32Array([5, 5, 5]),
      clusterIds: ['1'],
      sliceIds: ['s0'],
    };

    const viz_state = makeViewState({ selected_cluster_ids: new Set(['1']) });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);
    fetchedUrls.length = 0;
    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]);
  });
});

describe('neighborhood-cloud multi-cluster ("meta-cluster") cell centroid loading', () => {
  let refresh_nbhd_cloud_cluster_cells;
  const fetchedUrls = [];
  const tablesByUrl = {};

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = readStripped('../deck-gl/layers/nbhd_cloud_cell_layer.js');

    // Unlike the single-cluster describe block above, parse_cells_tables
    // here is keyed by the fetched URL (not one shared box) -- a
    // meta-cluster selection fetches more than one cluster's file at once,
    // each of which needs its own cell data back.
    const shims = `
      const options = { fetch: {} };
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_cells_tables = ([table]) => tablesByUrl[table.url];
      const getModelMatrixProps = () => ({});
    `;

    const code = `${shims}\n${source}\nmodule.exports = { refresh_nbhd_cloud_cluster_cells };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', 'tablesByUrl', code)(
      module,
      module.exports,
      fetchedUrls,
      tablesByUrl
    );
    ({ refresh_nbhd_cloud_cluster_cells } = module.exports);
  });

  beforeEach(() => {
    fetchedUrls.length = 0;
  });

  const makeLayersObj = () => ({
    nbhd_cloud_cell_layer: {
      clone(props) {
        return { ...this, ...props };
      },
    },
  });

  test('merges cells from every selected cluster, each keeping its own cluster color', async () => {
    tablesByUrl[
      'http://example.test/nbhd_cloud/cells/by_cluster/cluster_1.parquet'
    ] = {
      length: 1,
      positions: new Float32Array([1, 1, 1]),
      clusterIds: ['1'],
      sliceIds: ['s0'],
    };
    tablesByUrl[
      'http://example.test/nbhd_cloud/cells/by_cluster/cluster_2.parquet'
    ] = {
      length: 2,
      positions: new Float32Array([2, 2, 2, 3, 3, 3]),
      clusterIds: ['2', '2'],
      sliceIds: ['s0', 's1'],
    };

    const viz_state = {
      nbhd_cloud: { selected_cluster_ids: new Set(['1', '2']) },
      cats: { color_dict_cluster: { 1: [10, 20, 30], 2: [40, 50, 60] } },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

    expect([...fetchedUrls].sort()).toEqual([
      'http://example.test/nbhd_cloud/cells/by_cluster/cluster_1.parquet',
      'http://example.test/nbhd_cloud/cells/by_cluster/cluster_2.parquet',
    ]);

    const { data } = layers_obj.nbhd_cloud_cell_layer;
    expect(data.length).toBe(3);
    expect(Array.from(data.attributes.getPosition.value)).toEqual([
      1, 1, 1, 2, 2, 2, 3, 3, 3,
    ]);
    expect(Array.from(data.attributes.getColor.value)).toEqual([
      10, 20, 30, 255, 40, 50, 60, 255, 40, 50, 60, 255,
    ]);
  });
});

describe('neighborhood-cloud gene-selected cell centroid loading ("peppering")', () => {
  let refresh_nbhd_cloud_gene_cells;
  let update_nbhd_cloud_cell_layer_opacity;
  const fetchedUrls = [];
  const cellsBox = { value: null };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ')
        .replace(/^export function /gm, 'function ');

    // Real toExpressionByte (not shimmed) -- the actual normalization logic
    // is exactly what's under test for gene-cell coloring.
    const source = [
      readStripped('../global_variables/cell_exp_array.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_cell_layer.js'),
    ].join('\n');

    const shims = `
      const options = { fetch: {} };
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_cells_tables = () => cellsBox.value;
      const parse_gene_cells_table = () => cellsBox.value;
      const getModelMatrixProps = () => ({});
    `;

    const code = `${shims}\n${source}\nmodule.exports = { refresh_nbhd_cloud_gene_cells, update_nbhd_cloud_cell_layer_opacity };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', 'cellsBox', code)(
      module,
      module.exports,
      fetchedUrls,
      cellsBox
    );
    ({ refresh_nbhd_cloud_gene_cells, update_nbhd_cloud_cell_layer_opacity } =
      module.exports);
  });

  beforeEach(() => {
    fetchedUrls.length = 0;
  });

  const makeViewState = (nbhd_cloud_overrides = {}) => ({
    nbhd_cloud: { gene_shapes_mode: true, ...nbhd_cloud_overrides },
    global_base_url: 'http://example.test',
    aws: null,
  });

  const makeLayersObj = () => ({
    nbhd_cloud_cell_layer: {
      clone(props) {
        return { ...this, ...props };
      },
    },
  });

  test('no gene selected -> clears the layer without fetching', async () => {
    const viz_state = makeViewState({ selected_gene: null });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]);
    expect(layers_obj.nbhd_cloud_cell_layer.data.length).toBe(0);
  });

  test('fetches cells/by_gene and colors each cell red, alpha by its own expression', async () => {
    cellsBox.value = {
      length: 2,
      positions: new Float32Array([1, 1, 1, 2, 2, 2]),
      sliceIds: ['s0', 's1'],
      expressions: [10, 0],
    };

    const viz_state = makeViewState({
      selected_gene: 'Matn1',
      available_gene_shapes: new Map([['Matn1', 10]]),
    });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/cells/by_gene/Matn1.parquet',
    ]);

    const { data } = layers_obj.nbhd_cloud_cell_layer;
    expect(data.length).toBe(2);
    const colors = Array.from(data.attributes.getColor.value);
    // log1p(10)/log1p(10) * 255 = 255 at the manifest max.
    expect(colors.slice(0, 4)).toEqual([255, 0, 0, 255]);
    // 0 expression -> 0 alpha regardless of max.
    expect(colors.slice(4, 8)).toEqual([255, 0, 0, 0]);
  });

  test('an active slice selection narrows the gene-cell fetch to that slice, client-side', async () => {
    cellsBox.value = {
      length: 3,
      positions: new Float32Array([1, 1, 1, 2, 2, 2, 3, 3, 3]),
      sliceIds: ['s0', 's1', 's0'],
      expressions: [5, 5, 5],
    };

    const viz_state = makeViewState({
      selected_gene: 'Matn1',
      available_gene_shapes: new Map([['Matn1', 10]]),
      selected_slice_ids: new Set(['s0']),
    });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);

    const { data } = layers_obj.nbhd_cloud_cell_layer;
    expect(data.length).toBe(2);
    expect(Array.from(data.attributes.getPosition.value)).toEqual([
      1, 1, 1, 3, 3, 3,
    ]);
  });

  test('a second call for the same gene reuses the cached fetch', async () => {
    cellsBox.value = {
      length: 1,
      positions: new Float32Array([5, 5, 5]),
      sliceIds: ['s0'],
      expressions: [5],
    };

    const viz_state = makeViewState({
      selected_gene: 'Matn1',
      available_gene_shapes: new Map([['Matn1', 10]]),
    });
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);
    fetchedUrls.length = 0;
    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]);
  });

  test('gene-mode opacity comes straight from gene_fill_opacity, no cluster-mode dampening', () => {
    const viz_state = makeViewState({ gene_fill_opacity: 0.5 });
    const layers_obj = makeLayersObj();

    update_nbhd_cloud_cell_layer_opacity(layers_obj, viz_state);

    expect(layers_obj.nbhd_cloud_cell_layer.opacity).toBe(0.5);
  });

  test('a scatter-only gene (no shape entry) normalizes against available_gene_scatter instead', async () => {
    cellsBox.value = {
      length: 1,
      positions: new Float32Array([1, 1, 1]),
      sliceIds: ['s0'],
      expressions: [30],
    };

    const viz_state = {
      nbhd_cloud: {
        gene_shapes_mode: false,
        gene_scatter_mode: true,
        selected_gene: 'Actb',
        available_gene_shapes: new Map(), // no shape entry for Actb
        available_gene_scatter: new Map([['Actb', 30]]),
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);

    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/cells/by_gene/Actb.parquet',
    ]);
    const colors = Array.from(
      layers_obj.nbhd_cloud_cell_layer.data.attributes.getColor.value
    );
    // Expression equals the scatter manifest's max -> full alpha, same as
    // the shape-backed path would give at its own manifest's max.
    expect(colors).toEqual([255, 0, 0, 255]);
  });

  test('gene_scatter_mode opacity also skips cluster-mode dampening, same as gene_shapes_mode', () => {
    const viz_state = {
      nbhd_cloud: { gene_scatter_mode: true, gene_fill_opacity: 0.5 },
    };
    const layers_obj = makeLayersObj();

    update_nbhd_cloud_cell_layer_opacity(layers_obj, viz_state);

    expect(layers_obj.nbhd_cloud_cell_layer.opacity).toBe(0.5);
  });
});
