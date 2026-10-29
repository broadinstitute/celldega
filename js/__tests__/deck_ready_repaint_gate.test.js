/* global require */

// deck_ready is the Landscape's only general repaint signal: its subscriber
// (landscape_ist.js) calls deck.setProps({ layers }) when it flips true.
// These tests pin the store contract that makes the refresh_layer
// false→true toggle mandatory for programmatic redraws: deck_ready is a
// boolean Observable whose set() skips equal values, so a true-only
// deck_check write in steady state must NOT re-emit deck_ready — the bug
// that left update_matrix_gene's expression colors unrendered until an
// unrelated interaction repainted (celldega-app gene-click lag).

describe('deck_check → deck_ready repaint gate', () => {
  let create_obs_store;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(path.join(__dirname, '../obs_store/obs_store.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { create_obs_store };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ create_obs_store } = module.exports);
  });

  const subscribe_ready = (store) => {
    const emissions = [];
    store.deck_ready.subscribe((ready) => emissions.push(ready), {
      immediate: false,
    });
    return emissions;
  };

  test('a true-only deck_check write in steady state does not emit deck_ready', () => {
    const store = create_obs_store();
    // Reach steady state: all flags start true, so one write brings
    // deck_ready from its initial false to true.
    store.deck_check.set({ ...store.deck_check.get() });
    const emissions = subscribe_ready(store);

    store.deck_check.set({ ...store.deck_check.get(), cell_layer: true });

    expect(emissions).toEqual([]);
  });

  test('the refresh_layer false→true toggle emits a repaint transition', () => {
    const store = create_obs_store();
    store.deck_check.set({ ...store.deck_check.get() });
    const emissions = subscribe_ready(store);

    store.deck_check.set({ ...store.deck_check.get(), cell_layer: false });
    store.deck_check.set({ ...store.deck_check.get(), cell_layer: true });

    expect(emissions).toEqual([false, true]);
  });

  test('a toggle completes only once every other pending layer is ready', () => {
    const store = create_obs_store();
    store.deck_check.set({ ...store.deck_check.get() });
    const emissions = subscribe_ready(store);

    // A transcript tile load is still in flight when the gene toggle runs.
    store.deck_check.set({ ...store.deck_check.get(), trx_layer: false });
    store.deck_check.set({ ...store.deck_check.get(), cell_layer: false });
    store.deck_check.set({ ...store.deck_check.get(), cell_layer: true });
    expect(emissions).toEqual([false]);

    // The pending load finishing supplies the false→true repaint transition.
    store.deck_check.set({ ...store.deck_check.get(), trx_layer: true });
    expect(emissions).toEqual([false, true]);
  });
});

describe('image visibility on gene selections', () => {
  let create_obs_store;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(path.join(__dirname, '../obs_store/obs_store.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { create_obs_store };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ create_obs_store } = module.exports);
  });

  test('only a single-gene (expression-colored) selection hides the images', () => {
    const store = create_obs_store();
    store.setup_image_visibility_manager(() => true);

    // Multi-gene selection (row dendrogram / crop sync) stays in cluster
    // coloring — the background images must not black out.
    store.selected_genes.set(['g0', 'g1', 'g2']);
    expect(store.viz_image_layers.get()).toBe(true);

    // A single gene drives expression coloring: hide images when zoomed out.
    store.selected_genes.set(['g0']);
    expect(store.viz_image_layers.get()).toBe(false);

    // Back to a multi-gene set restores the images.
    store.selected_genes.set(['g0', 'g1']);
    expect(store.viz_image_layers.get()).toBe(true);
  });
});
