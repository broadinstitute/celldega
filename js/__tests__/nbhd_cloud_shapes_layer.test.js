/* global require */

describe('neighborhood-cloud shapes fill color', () => {
  let is_nbhd_cloud_gene_color_mode;
  let get_nbhd_cloud_fill_color;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    // Shims for imports not exercised by these tests (refresh_layer, the
    // cell-layer cross-import) -- the file under test calls them only from
    // functions these tests don't invoke.
    const shims = `
      const refresh_layer = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { is_nbhd_cloud_gene_color_mode, get_nbhd_cloud_fill_color };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ is_nbhd_cloud_gene_color_mode, get_nbhd_cloud_fill_color } =
      module.exports);
  });

  const feature = (color, cluster_id = '1', neighborhood_id = 's0__1') => ({
    properties: { color, cluster_id, neighborhood_id },
  });

  test('is_nbhd_cloud_gene_color_mode is false when no gene selected', () => {
    expect(is_nbhd_cloud_gene_color_mode({})).toBe(false);
    expect(is_nbhd_cloud_gene_color_mode({ selected_gene: null })).toBe(false);
  });

  test('is_nbhd_cloud_gene_color_mode is true once a gene is selected', () => {
    expect(is_nbhd_cloud_gene_color_mode({ selected_gene: 'Gene0' })).toBe(
      true
    );
  });

  test('cluster-color mode: fill uses the neighborhood color, alpha scaled by manual_fill_opacity', () => {
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000'), { nbhd_cloud: {} })
    ).toEqual([255, 0, 0, 255]);
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000'), {
        nbhd_cloud: { manual_fill_opacity: 0.5 },
      })
    ).toEqual([255, 0, 0, 128]);
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000'), {
        nbhd_cloud: { manual_fill_opacity: 0 },
      })
    ).toEqual([255, 0, 0, 0]);
  });

  test('gene-color mode: alpha is expression fraction times manual_fill_opacity', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Gene0',
        selected_gene_max_mean: 10,
        gene_stats: new Map([['s0__1', { mean: 5, variance: 0 }]]),
      },
    };

    // manual_fill_opacity defaults to 1: alpha = 255 * (5/10) * 1
    expect(
      get_nbhd_cloud_fill_color(feature('#00ff00', '1', 's0__1'), viz_state)
    ).toEqual([255, 0, 0, 128]);

    viz_state.nbhd_cloud.manual_fill_opacity = 0.5;
    // alpha = 255 * (5/10) * 0.5
    expect(
      get_nbhd_cloud_fill_color(feature('#00ff00', '1', 's0__1'), viz_state)
    ).toEqual([255, 0, 0, 64]);
  });

  test('gene-color mode: neighborhoods with no stats for the selected gene get zero alpha', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Gene0',
        selected_gene_max_mean: 10,
        gene_stats: new Map(),
      },
    };

    expect(
      get_nbhd_cloud_fill_color(feature('#00ff00', '1', 'missing'), viz_state)
    ).toEqual([255, 0, 0, 0]);
  });

  test('a selected cluster stays fully opaque; unselected clusters are fully hidden -- across every slice', () => {
    const viz_state = {
      nbhd_cloud: { selected_cluster_ids: new Set(['1']) },
    };

    // cluster 1, whichever slice, stays full opacity
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', '1', 's0__1'), viz_state)
    ).toEqual([255, 0, 0, 255]);
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', '1', 's5__1'), viz_state)
    ).toEqual([255, 0, 0, 255]);
    // cluster 2 is fully hidden while a selection is active
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', '2', 's0__2'), viz_state)
    ).toEqual([255, 0, 0, 0]);
  });

  test("gene-shapes mode: alpha comes from the feature's own mean_expression, not a neighborhood lookup", () => {
    const geneFeature = (mean_expression) => ({
      properties: { gene: 'Matn1', slice_id: 's0', mean_expression },
    });
    const viz_state = {
      nbhd_cloud: { gene_shapes_mode: true, gene_shapes_max_mean: 10 },
    };

    expect(get_nbhd_cloud_fill_color(geneFeature(5), viz_state)).toEqual([
      255, 0, 0, 128,
    ]);
    expect(get_nbhd_cloud_fill_color(geneFeature(10), viz_state)).toEqual([
      255, 0, 0, 255,
    ]);

    viz_state.nbhd_cloud.manual_fill_opacity = 0.5;
    expect(get_nbhd_cloud_fill_color(geneFeature(10), viz_state)).toEqual([
      255, 0, 0, 128,
    ]);
  });
});

describe('neighborhood-cloud cluster-select / gene-select mutual exclusion', () => {
  let toggle_nbhd_cloud_cluster_selection;
  let select_nbhd_cloud_gene;
  const cellRefreshCalls = [];
  const geneTable = { name: 'Gene0' };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    const shims = `
      const options = { fetch: {} };
      const refresh_layer = () => {};
      const get_arrow_table = async () => geneTable;
      const parse_gene_expression_table = () => new Map([['s0__1', { mean: 5, variance: 0 }]]);
      const refresh_nbhd_cloud_cluster_cells = async () => { cellRefreshCalls.push(true); };
    `;

    const code = `${shims}\n${source}\nmodule.exports = { toggle_nbhd_cloud_cluster_selection, select_nbhd_cloud_gene };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'geneTable', 'cellRefreshCalls', code)(
      module,
      module.exports,
      geneTable,
      cellRefreshCalls
    );
    ({ toggle_nbhd_cloud_cluster_selection, select_nbhd_cloud_gene } =
      module.exports);
  });

  beforeEach(() => {
    cellRefreshCalls.length = 0;
  });

  const makeLayersObj = () => ({
    nbhd_cloud_shapes_layer: {
      clone(props) {
        return { ...this, ...props };
      },
    },
  });

  test('selecting a cluster clears any active gene selection', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Gene0',
        gene_stats: new Map([['s0__1', { mean: 5 }]]),
        selected_gene_max_mean: 5,
      },
    };

    toggle_nbhd_cloud_cluster_selection('1', viz_state, makeLayersObj());

    expect(viz_state.nbhd_cloud.selected_cluster_ids).toEqual(new Set(['1']));
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(viz_state.nbhd_cloud.gene_stats).toBeNull();
    expect(viz_state.nbhd_cloud.selected_gene_max_mean).toBe(0);
  });

  test('selecting a gene clears any active cluster selection and its cell centroids', async () => {
    const viz_state = {
      nbhd_cloud: { selected_cluster_ids: new Set(['1']) },
      global_base_url: 'http://example.test',
      aws: null,
    };

    await select_nbhd_cloud_gene('Gene0', viz_state, makeLayersObj());

    expect(viz_state.nbhd_cloud.selected_gene).toBe('Gene0');
    expect(viz_state.nbhd_cloud.selected_cluster_ids.size).toBe(0);
    expect(cellRefreshCalls).toEqual([true]);
  });
});

describe('neighborhood-cloud gene-shapes mode (curated marker-gene list)', () => {
  let select_nbhd_cloud_gene;
  const fetchedUrls = [];
  const geneShapeFeatures = [
    { properties: { gene: 'Matn1', slice_id: 's0', mean_expression: 5 } },
    { properties: { gene: 'Matn1', slice_id: 's1', mean_expression: 10 } },
  ];

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    const shims = `
      const options = { fetch: {} };
      const refresh_layer = () => {};
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_gene_expression_table = () => new Map();
      const parse_gene_shapes_table_to_features = () => geneShapeFeatures;
      const refresh_nbhd_cloud_cluster_cells = async () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { select_nbhd_cloud_gene };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', 'geneShapeFeatures', code)(
      module,
      module.exports,
      fetchedUrls,
      geneShapeFeatures
    );
    ({ select_nbhd_cloud_gene } = module.exports);
  });

  beforeEach(() => {
    fetchedUrls.length = 0;
  });

  const makeLayersObj = () => ({
    nbhd_cloud_shapes_layer: {
      clone(props) {
        return { ...this, ...props };
      },
    },
  });

  test('a gene with precomputed shapes swaps the layer data and colors by its own mean_expression', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Set(['Matn1']),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj);

    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/gene_shapes/Matn1.parquet',
    ]);
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(true);
    expect(viz_state.nbhd_cloud.gene_shapes_max_mean).toBe(10);
    expect(layers_obj.nbhd_cloud_shapes_layer.data.features).toBe(
      geneShapeFeatures
    );
  });

  test('clicking the same gene again reverts to the cluster shapes', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Set(['Matn1']),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj);
    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj);

    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(false);
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(layers_obj.nbhd_cloud_shapes_layer.data.features).toBe(
      viz_state.nbhd_cloud.shapes_features
    );
  });

  test('a gene without precomputed shapes does not fetch gene_shapes and leaves gene_shapes_mode off', async () => {
    const viz_state = {
      nbhd_cloud: {
        gene_shapes_mode: false,
        available_gene_shapes: new Set(['Matn1']),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('SomeOtherGene', viz_state, layers_obj);

    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/expression/SomeOtherGene.parquet',
    ]);
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(false);
  });
});
