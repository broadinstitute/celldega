/* global require */

describe('neighborhood-cloud per-neighborhood cell centroid loading', () => {
  let select_nbhd_cloud_neighborhood_cells;
  const fetchedUrls = [];
  const cellsBox = { value: null };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import .*$/gm, '')
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

    const code = `${shims}\n${source}\nmodule.exports = { select_nbhd_cloud_neighborhood_cells };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', 'cellsBox', code)(
      module,
      module.exports,
      fetchedUrls,
      cellsBox
    );
    ({ select_nbhd_cloud_neighborhood_cells } = module.exports);
  });

  beforeEach(() => {
    fetchedUrls.length = 0;
  });

  const makeViewState = () => ({
    nbhd_cloud: {},
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

  test('fetches by_slice, filters to the picked cluster, and colors by cluster', async () => {
    cellsBox.value = {
      length: 3,
      positions: new Float32Array([1, 1, 1, 2, 2, 2, 3, 3, 3]),
      clusterIds: ['1', '2', '1'],
      sliceIds: ['s0', 's0', 's0'],
    };

    const viz_state = makeViewState();
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_neighborhood_cells(
      's0__1',
      's0',
      '1',
      viz_state,
      layers_obj
    );

    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/cells/by_slice/slice_s0.parquet',
    ]);

    const { data } = layers_obj.nbhd_cloud_cell_layer;
    expect(data.length).toBe(2);
    expect(Array.from(data.attributes.getPosition.value)).toEqual([
      1, 1, 1, 3, 3, 3,
    ]);
    expect(Array.from(data.attributes.getColor.value)).toEqual([
      10, 20, 30, 255, 10, 20, 30, 255,
    ]);
  });

  test('clicking the same neighborhood again clears the layer without refetching', async () => {
    cellsBox.value = {
      length: 1,
      positions: new Float32Array([1, 1, 1]),
      clusterIds: ['1'],
      sliceIds: ['s0'],
    };

    const viz_state = makeViewState();
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_neighborhood_cells(
      's0__1',
      's0',
      '1',
      viz_state,
      layers_obj
    );
    fetchedUrls.length = 0;

    await select_nbhd_cloud_neighborhood_cells(
      's0__1',
      's0',
      '1',
      viz_state,
      layers_obj
    );

    expect(fetchedUrls).toEqual([]);
    expect(layers_obj.nbhd_cloud_cell_layer.data.length).toBe(0);
  });

  test('a second selection for the same slice reuses the cached fetch', async () => {
    cellsBox.value = {
      length: 2,
      positions: new Float32Array([5, 5, 5, 6, 6, 6]),
      clusterIds: ['1', '2'],
      sliceIds: ['s1', 's1'],
    };

    const viz_state = makeViewState();
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_neighborhood_cells(
      's1__1',
      's1',
      '1',
      viz_state,
      layers_obj
    );
    // reset the selection so the next call doesn't just clear it
    await select_nbhd_cloud_neighborhood_cells(
      's1__1',
      's1',
      '1',
      viz_state,
      layers_obj
    );
    fetchedUrls.length = 0;

    await select_nbhd_cloud_neighborhood_cells(
      's1__2',
      's1',
      '2',
      viz_state,
      layers_obj
    );

    expect(fetchedUrls).toEqual([]);
    expect(layers_obj.nbhd_cloud_cell_layer.data.length).toBe(1);
  });
});
