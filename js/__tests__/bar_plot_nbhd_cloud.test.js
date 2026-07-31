/* global require */

describe('neighborhood-cloud slice bar refreshes the currently-relevant cell layer', () => {
  let bar_callback_nbhd_cloud_slice;
  const calls = { cluster: 0, gene: 0 };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = readStripped('../ui/bar_plot.js');

    // Every import bar_plot.js has is shimmed -- this test only exercises
    // bar_callback_nbhd_cloud_slice's own branching logic (which cell-layer
    // refresh function it picks based on gene_shapes_mode), not any of the
    // modules it delegates to.
    const shims = `
      const new_toggle_cell_layer_visibility = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => { calls.cluster += 1; };
      const refresh_nbhd_cloud_gene_cells = async () => { calls.gene += 1; };
      const apply_nbhd_cloud_slice_filter = () => {};
      const select_nbhd_cloud_gene = async () => {};
      const toggle_nbhd_cloud_cluster_selection = () => {};
      const toggle_trx_layer_visibility = () => {};
      const update_cat = () => {};
      const update_selected_cats = () => {};
      const update_cell_exp_array = () => {};
      const update_selected_genes = () => {};
      const toggle_slider = () => {};
      const refresh_layer = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { bar_callback_nbhd_cloud_slice };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'calls', code)(
      module,
      module.exports,
      calls
    );
    ({ bar_callback_nbhd_cloud_slice } = module.exports);
  });

  beforeEach(() => {
    calls.cluster = 0;
    calls.gene = 0;
  });

  const makeViewState = (nbhd_cloud_overrides = {}) => ({
    nbhd_cloud: {
      svg_bar_slice: { selectAll: () => ({ style: () => {} }) },
      ...nbhd_cloud_overrides,
    },
  });

  test('cluster-color mode: isolating a slice refreshes cluster cells, not gene cells', async () => {
    const viz_state = makeViewState({ gene_shapes_mode: false });

    await bar_callback_nbhd_cloud_slice(
      null,
      { name: 's0' },
      null,
      {},
      viz_state
    );

    expect(calls.cluster).toBe(1);
    expect(calls.gene).toBe(0);
  });

  test('gene-shapes mode: isolating a slice refreshes the peppered gene cells, not cluster cells', async () => {
    const viz_state = makeViewState({
      gene_shapes_mode: true,
      selected_gene: 'Matn1',
    });

    await bar_callback_nbhd_cloud_slice(
      null,
      { name: 's0' },
      null,
      {},
      viz_state
    );

    expect(calls.gene).toBe(1);
    expect(calls.cluster).toBe(0);
  });
});

describe('neighborhood-cloud gene bar drives the shared Uniprot gene-info panel', () => {
  let bar_callback_gene;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    // Real update_selected_genes (not shimmed) -- its own same-array-means-
    // toggle-off heuristic is exactly what this fix has to avoid tripping
    // on the "gene unavailable, no-op" case.
    const source = [
      readStripped('../global_variables/selected_genes.js'),
      readStripped('../ui/bar_plot.js'),
    ].join('\n');

    // select_nbhd_cloud_gene is faked to mimic the real contract: it's a
    // no-op (leaves nbhd_cloud.selected_gene untouched) for a gene not in
    // available_gene_shapes, otherwise it resets to null (same gene
    // clicked again) or sets the new gene.
    const shims = `
      const new_toggle_cell_layer_visibility = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
      const apply_nbhd_cloud_slice_filter = () => {};
      const select_nbhd_cloud_gene = async (gene, viz_state) => {
        const { nbhd_cloud } = viz_state;
        if (gene === nbhd_cloud.selected_gene) {
          nbhd_cloud.selected_gene = null;
        } else if (nbhd_cloud.available_gene_shapes?.has(gene)) {
          nbhd_cloud.selected_gene = gene;
        }
      };
      const toggle_nbhd_cloud_cluster_selection = () => {};
      const toggle_trx_layer_visibility = () => {};
      const update_cat = () => {};
      const update_selected_cats = () => {};
      const update_cell_exp_array = () => {};
      const toggle_slider = () => {};
      const refresh_layer = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { bar_callback_gene };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ bar_callback_gene } = module.exports);
  });

  const fakeRects = () => ({
    selectAll: () => ({ style: () => {} }),
  });

  let obsSelectedGenes;

  const makeViewState = (nbhd_cloud_overrides = {}) => ({
    nbhd_cloud: {
      is_nbhd_cloud: true,
      svg_bar_cluster: fakeRects(),
      ...nbhd_cloud_overrides,
    },
    sliders: { nbhd: {}, trx: {} },
    genes: { svg_bar_gene: fakeRects(), selected_genes: [] },
    obs_store: { selected_genes: { set: (v) => obsSelectedGenes.push(v) } },
  });

  beforeEach(() => {
    obsSelectedGenes = [];
  });

  test('selecting an available gene pushes it to obs_store.selected_genes', async () => {
    const viz_state = makeViewState({
      available_gene_shapes: new Map([['Matn1', 10]]),
    });

    await bar_callback_gene(null, { name: 'Matn1' }, null, {}, viz_state);

    expect(obsSelectedGenes).toEqual([['Matn1']]);
  });

  test('clicking the same gene again (reset) clears obs_store.selected_genes', async () => {
    const viz_state = makeViewState({
      available_gene_shapes: new Map([['Matn1', 10]]),
    });

    await bar_callback_gene(null, { name: 'Matn1' }, null, {}, viz_state);
    obsSelectedGenes = [];
    await bar_callback_gene(null, { name: 'Matn1' }, null, {}, viz_state);

    expect(obsSelectedGenes).toEqual([[]]);
  });

  test('a gene with no precomputed shapes is a no-op: obs_store is left untouched', async () => {
    const viz_state = makeViewState({
      available_gene_shapes: new Map([['Matn1', 10]]),
    });

    await bar_callback_gene(null, { name: 'Unknown' }, null, {}, viz_state);

    expect(obsSelectedGenes).toEqual([]);
    expect(viz_state.nbhd_cloud.selected_gene).toBeUndefined();
  });

  test('switching from gene A to gene B pushes B, not a toggle-off', async () => {
    const viz_state = makeViewState({
      available_gene_shapes: new Map([
        ['Matn1', 10],
        ['Col1a1', 5],
      ]),
    });

    await bar_callback_gene(null, { name: 'Matn1' }, null, {}, viz_state);
    obsSelectedGenes = [];
    await bar_callback_gene(null, { name: 'Col1a1' }, null, {}, viz_state);

    expect(obsSelectedGenes).toEqual([['Col1a1']]);
  });
});
