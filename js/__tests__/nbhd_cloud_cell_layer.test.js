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
