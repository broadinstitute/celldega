/* global require */

describe('neighborhood-cloud shapes fill color', () => {
  let get_nbhd_cloud_fill_color;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ')
        .replace(/^export function /gm, 'function ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../global_variables/cell_exp_array.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    // Shims for imports not exercised by these tests (refresh_layer, the
    // cell-layer cross-import) -- the file under test calls them only from
    // functions these tests don't invoke.
    const shims = `
      const refresh_layer = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { get_nbhd_cloud_fill_color };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_nbhd_cloud_fill_color } = module.exports);
  });

  const feature = (color, cluster_id = '1') => ({
    properties: { color, cluster_id },
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

  test('a selected cluster stays fully opaque; unselected clusters are fully hidden -- across every slice', () => {
    const viz_state = {
      nbhd_cloud: { selected_cluster_ids: new Set(['1']) },
    };

    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', '1'), viz_state)
    ).toEqual([255, 0, 0, 255]);
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', '2'), viz_state)
    ).toEqual([255, 0, 0, 0]);
  });

  test("gene-shapes mode: flat alpha from gene_fill_opacity, regardless of the feature's own mean_expression", () => {
    const geneFeature = (mean_expression) => ({
      properties: { gene: 'Matn1', slice_id: 's0', mean_expression },
    });
    const viz_state = {
      nbhd_cloud: {
        gene_shapes_mode: true,
        available_gene_shapes: new Map([['Matn1', 10]]),
      },
    };

    // Full opacity regardless of mean_expression -- the shape's boundary
    // already encodes "expressing >= min_expression", so alpha doesn't
    // additionally scale with how strongly a shape expresses.
    expect(get_nbhd_cloud_fill_color(geneFeature(10), viz_state)).toEqual([
      255, 0, 0, 255,
    ]);
    expect(get_nbhd_cloud_fill_color(geneFeature(0), viz_state)).toEqual([
      255, 0, 0, 255,
    ]);

    viz_state.nbhd_cloud.gene_fill_opacity = 0.5;
    expect(get_nbhd_cloud_fill_color(geneFeature(10), viz_state)).toEqual([
      255, 0, 0, 128,
    ]);
  });
});

describe('build_nbhd_cloud_gene_bar_data', () => {
  let build_nbhd_cloud_gene_bar_data;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ')
        .replace(/^export function /gm, 'function ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../global_variables/cell_exp_array.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    const shims = `
      const refresh_layer = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { build_nbhd_cloud_gene_bar_data };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ build_nbhd_cloud_gene_bar_data } = module.exports);
  });

  test('merges shape-backed and scatter-only genes into one bar list', () => {
    const bars = build_nbhd_cloud_gene_bar_data({
      available_gene_shapes: new Map([['Matn1', 10]]),
      available_gene_scatter: new Map([['Actb', 60]]),
    });

    expect(new Set(bars.map((b) => b.name))).toEqual(
      new Set(['Matn1', 'Actb'])
    );
    expect(bars.find((b) => b.name === 'Matn1').value).toBe(10);
    expect(bars.find((b) => b.name === 'Actb').value).toBe(60);
  });

  test('a gene in both manifests keeps the shape-backed value', () => {
    const bars = build_nbhd_cloud_gene_bar_data({
      available_gene_shapes: new Map([['Matn1', 10]]),
      available_gene_scatter: new Map([['Matn1', 999]]),
    });

    expect(bars).toEqual([{ name: 'Matn1', value: 10 }]);
  });

  test('empty/missing manifests produce an empty bar list', () => {
    expect(build_nbhd_cloud_gene_bar_data({})).toEqual([]);
    expect(build_nbhd_cloud_gene_bar_data(undefined)).toEqual([]);
  });
});

describe('neighborhood-cloud cluster-select / gene-select mutual exclusion', () => {
  let toggle_nbhd_cloud_cluster_selection;
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
        .replace(/^export const /gm, 'const ')
        .replace(/^export function /gm, 'function ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../global_variables/cell_exp_array.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    const shims = `
      const options = { fetch: {} };
      const refresh_layer = () => {};
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_gene_shapes_table_to_features = () => geneShapeFeatures;
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { toggle_nbhd_cloud_cluster_selection, select_nbhd_cloud_gene };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', 'geneShapeFeatures', code)(
      module,
      module.exports,
      fetchedUrls,
      geneShapeFeatures
    );
    ({ toggle_nbhd_cloud_cluster_selection, select_nbhd_cloud_gene } =
      module.exports);
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

  test('selecting a cluster clears any active gene-shapes selection and restores cluster shapes', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Matn1',
        gene_shapes_mode: true,
        shapes_features: [{ properties: { cluster_id: '1', color: '#000' } }],
      },
    };

    toggle_nbhd_cloud_cluster_selection('1', viz_state, makeLayersObj());

    expect(viz_state.nbhd_cloud.selected_cluster_ids).toEqual(new Set(['1']));
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(false);
  });

  test('selecting an available gene clears any active cluster selection and its cell centroids', async () => {
    const viz_state = {
      nbhd_cloud: {
        selected_cluster_ids: new Set(['1']),
        available_gene_shapes: new Map([['Matn1', 10]]),
        shapes_features: [],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };

    await select_nbhd_cloud_gene('Matn1', viz_state, makeLayersObj());

    expect(viz_state.nbhd_cloud.selected_gene).toBe('Matn1');
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(true);
    expect(viz_state.nbhd_cloud.selected_cluster_ids.size).toBe(0);
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
        .replace(/^export const /gm, 'const ')
        .replace(/^export function /gm, 'function ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../global_variables/cell_exp_array.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    const shims = `
      const options = { fetch: {} };
      const refresh_layer = () => {};
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_gene_shapes_table_to_features = () => geneShapeFeatures;
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
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

  test('a gene with precomputed shapes swaps the layer data', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Map([['Matn1', 10]]),
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
      'http://example.test/nbhd_cloud/shapes/by_gene/Matn1.parquet',
    ]);
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(true);
    expect(layers_obj.nbhd_cloud_shapes_layer.data.features).toBe(
      geneShapeFeatures
    );
  });

  test('clicking the same gene again reverts to the cluster shapes', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Map([['Matn1', 10]]),
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

  test('a gene without precomputed shapes is a no-op: no fetch, no state change', async () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: null,
        gene_shapes_mode: false,
        available_gene_shapes: new Map([['Matn1', 10]]),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('SomeOtherGene', viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]);
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(false);
    expect(layers_obj.nbhd_cloud_shapes_layer.data).toBeUndefined();
  });

  test('a second selection for the same gene reuses the cached fetch', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Map([['Matn1', 10]]),
        shapes_features: [],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj);
    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj); // reset
    fetchedUrls.length = 0;
    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj); // select again

    expect(fetchedUrls).toEqual([]);
  });
});

describe('neighborhood-cloud gene cell-scatter mode (no shape, capped cell scatter)', () => {
  let select_nbhd_cloud_gene;
  let toggle_nbhd_cloud_cluster_selection;
  const fetchedUrls = [];

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ')
        .replace(/^export function /gm, 'function ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../global_variables/cell_exp_array.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    // A gene with only a cell scatter never reaches get_arrow_table/
    // parse_gene_shapes_table_to_features at all (no shape file exists for
    // it) -- get_arrow_table still tracks calls so a test can assert it was
    // never invoked for the shapes endpoint.
    const shims = `
      const options = { fetch: {} };
      const refresh_layer = () => {};
      const get_arrow_table = async (url) => { fetchedUrls.push(url); return { url }; };
      const parse_gene_shapes_table_to_features = () => [];
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { select_nbhd_cloud_gene, toggle_nbhd_cloud_cluster_selection };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'fetchedUrls', code)(
      module,
      module.exports,
      fetchedUrls
    );
    ({ select_nbhd_cloud_gene, toggle_nbhd_cloud_cluster_selection } =
      module.exports);
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

  test('a scatter-only gene sets gene_scatter_mode, not gene_shapes_mode, and never fetches a shape', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Map(),
        available_gene_scatter: new Map([['Actb', 60]]),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('Actb', viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]); // no shapes/by_gene fetch for a scatter-only gene
    expect(viz_state.nbhd_cloud.selected_gene).toBe('Actb');
    expect(viz_state.nbhd_cloud.gene_scatter_mode).toBe(true);
    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(false);
    // No shape to show -- the shapes layer goes empty rather than keeping
    // the cluster shapes (or a stale gene shape) on screen underneath.
    expect(layers_obj.nbhd_cloud_shapes_layer.data.features).toEqual([]);
  });

  test('clicking the same scatter-only gene again reverts to the cluster shapes', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Map(),
        available_gene_scatter: new Map([['Actb', 60]]),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('Actb', viz_state, layers_obj);
    await select_nbhd_cloud_gene('Actb', viz_state, layers_obj);

    expect(viz_state.nbhd_cloud.gene_scatter_mode).toBe(false);
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(layers_obj.nbhd_cloud_shapes_layer.data.features).toBe(
      viz_state.nbhd_cloud.shapes_features
    );
  });

  test('a gene in neither manifest is a no-op: no fetch, no state change', async () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: null,
        gene_scatter_mode: false,
        available_gene_shapes: new Map(),
        available_gene_scatter: new Map([['Actb', 60]]),
        shapes_features: [
          { properties: { cluster_id: '1', color: '#000000' } },
        ],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('NotAvailable', viz_state, layers_obj);

    expect(fetchedUrls).toEqual([]);
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(viz_state.nbhd_cloud.gene_scatter_mode).toBe(false);
    expect(layers_obj.nbhd_cloud_shapes_layer.data).toBeUndefined();
  });

  test('a gene present in both manifests is treated as shape-backed (shapes take precedence)', async () => {
    const viz_state = {
      nbhd_cloud: {
        available_gene_shapes: new Map([['Matn1', 10]]),
        available_gene_scatter: new Map([['Matn1', 10]]),
        shapes_features: [],
      },
      global_base_url: 'http://example.test',
      aws: null,
    };
    const layers_obj = makeLayersObj();

    await select_nbhd_cloud_gene('Matn1', viz_state, layers_obj);

    expect(viz_state.nbhd_cloud.gene_shapes_mode).toBe(true);
    expect(viz_state.nbhd_cloud.gene_scatter_mode).toBe(false);
    expect(fetchedUrls).toEqual([
      'http://example.test/nbhd_cloud/shapes/by_gene/Matn1.parquet',
    ]);
  });

  test('selecting a cluster while a scatter-only gene is active clears gene_scatter_mode and restores cluster shapes', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Actb',
        gene_scatter_mode: true,
        shapes_features: [{ properties: { cluster_id: '1', color: '#000' } }],
      },
    };

    toggle_nbhd_cloud_cluster_selection('1', viz_state, makeLayersObj());

    expect(viz_state.nbhd_cloud.selected_cluster_ids).toEqual(new Set(['1']));
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
    expect(viz_state.nbhd_cloud.gene_scatter_mode).toBe(false);
  });
});
