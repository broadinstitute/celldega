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
