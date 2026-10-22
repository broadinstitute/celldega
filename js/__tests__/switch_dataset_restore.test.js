/* global require */

// Restoring the gene selection after switching datasets (switch_dataset.js):
// the selection is reset for the switch and restored once the new dataset's
// expression loads, unless something was selected meanwhile.

const fs = require('fs');
const path = require('path');

const read_stripped = (rel_path) =>
  fs
    .readFileSync(path.join(__dirname, rel_path), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const calls = { restored: [], refreshed: 0 };
const control = { applied: true, pending: null };

const shims = `
  const update_cat = (cats, cat) => { cats.cat = cat; };
  const update_selected_cats = (cats, selected) => {
    cats.selected_cats = selected;
    calls.restored.push(['cats', [...selected]]);
  };
  const update_selected_genes = (genes, selected) => {
    genes.selected_genes = selected;
    calls.restored.push(['genes', [...selected]]);
  };
  const update_cell_exp_array = async () => {
    if (control.pending) await control.pending;
    return control.applied;
  };
  const refresh_cell_layer_data = () => { calls.refreshed += 1; };
`;
const module_ = { exports: {} };
new Function(
  'module',
  'calls',
  'control',
  `${shims}
${read_stripped('../global_variables/select_genes.js')}
${read_stripped('../ui/switch_dataset.js')}
module.exports = { restore_persistent_state };`
)(module_, calls, control);
const { restore_persistent_state } = module_.exports;

// The state switch_dataset leaves before restoring: nothing selected.
const make_viz_state = () => ({
  seg: { version: 'default' },
  umap: { has_umap: false },
  genes: { gene_names: ['A', 'B'], selected_genes: [] },
  cats: { cat: 'cluster', selected_cats: [], cluster_counts: [] },
  obs_store: {
    persistent_state: { set: () => {} },
    viz_image_layers: { get: () => true },
  },
});
const saved_state = {
  selected_genes: ['A', 'B', 'not-in-new-dataset'],
  selected_cats: ['A', 'B'],
  landscape_view: 'spatial',
};

describe('restore_persistent_state', () => {
  beforeEach(() => {
    calls.restored.length = 0;
    calls.refreshed = 0;
    control.applied = true;
    control.pending = null;
  });

  it('restores the genes found in the new dataset, summed', async () => {
    const viz_state = make_viz_state();
    await restore_persistent_state(viz_state, {}, saved_state);

    expect(viz_state.cats.cat).toBe('A + B');
    expect(calls.restored).toEqual([
      ['genes', ['A', 'B']],
      ['cats', ['A', 'B']],
    ]);
    expect(calls.refreshed).toBe(1);
  });

  it('keeps a cluster clicked while the expression loads', async () => {
    const viz_state = make_viz_state();
    let release;
    control.pending = new Promise((resolve) => {
      release = resolve;
    });
    const restoring = restore_persistent_state(viz_state, {}, saved_state);

    // A cluster bar click (no expression load).
    viz_state.cats.selected_cats = ['3'];
    release();
    await restoring;
    expect(calls.restored).toEqual([]);
    expect(viz_state.cats).toMatchObject({
      cat: 'cluster',
      selected_cats: ['3'],
    });
  });

  it('leaves the selection to a newer gene load', async () => {
    const viz_state = make_viz_state();
    control.applied = false;
    await restore_persistent_state(viz_state, {}, saved_state);
    expect(calls.restored).toEqual([]);
    expect(calls.refreshed).toBe(0);
  });
});
