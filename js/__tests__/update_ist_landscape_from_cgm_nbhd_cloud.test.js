/* global require */

// A Clustergram linked via `dega.viz.spatial_clustergram` drives Landscape /
// CellCloud / NeighborhoodCloud the same way: a jslink forwards its
// click_info straight onto the spatial widget's update_trigger, and
// update_ist_landscape_from_cgm.js decides what that click means. For
// NeighborhoodCloud, cluster/gene coloring lives entirely in
// nbhd_cloud_shapes_layer / nbhd_cloud_cell_layer (via nbhd_cloud_link.js),
// never in the generic per-cell path (update_cell_exp_array / cell_layer)
// used by Landscape and CellCloud -- this is exactly the bug reported:
// Clustergram clicks updated the gene bar graph / selection state but never
// the cloud's own coloring.
describe('update_ist_landscape_from_cgm routes neighborhood-cloud clicks to its own layers', () => {
  let update_ist_landscape_from_cgm;
  // Created once and mutated in place (not reassigned) -- the generated
  // function below closes over this exact object reference at `new
  // Function(...)` invocation time, which happens once in beforeAll.
  const calls = { generic: [], nbhd: [], refreshed: [] };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    // Real source for both the dispatcher under test and the nbhd_cloud
    // link helpers it now calls into -- only their own leaf dependencies
    // (deck.gl layer builders, network fetches) are shimmed below.
    const source = [
      readStripped('../widget_interactions/nbhd_cloud_link.js'),
      readStripped('../widget_interactions/update_ist_landscape_from_cgm.js'),
    ].join('\n');

    const shims = `
      const update_cat = (cats, cat) => { cats.cat = cat; calls.generic.push('update_cat'); };
      const update_selected_cats = () => { calls.generic.push('update_selected_cats'); };
      const update_selected_genes = (_genes, selected, obs_store) => {
        calls.generic.push('update_selected_genes');
        obs_store.selected_genes.set(selected);
      };
      const update_cell_exp_array = async () => { calls.generic.push('update_cell_exp_array'); };
      const handleAsyncError = (error) => { throw error; };
      const refresh_layer = (_viz_state, _layers_obj, name) => { calls.refreshed.push(name); };

      const set_nbhd_cloud_cluster_selection = (clusterIds, viz_state) => {
        viz_state.nbhd_cloud.selected_cluster_ids = new Set(clusterIds);
        calls.nbhd.push('set_nbhd_cloud_cluster_selection:' + clusterIds.join(','));
      };
      const refresh_nbhd_cloud_cluster_cells = async () => {
        calls.nbhd.push('refresh_nbhd_cloud_cluster_cells');
      };
      const select_nbhd_cloud_gene = async (gene, viz_state) => {
        viz_state.nbhd_cloud.selected_gene = gene;
        calls.nbhd.push('select_nbhd_cloud_gene:' + gene);
      };
      const sync_nbhd_cloud_opacity_sliders = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { update_ist_landscape_from_cgm };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'calls', code)(
      module,
      module.exports,
      calls
    );
    ({ update_ist_landscape_from_cgm } = module.exports);
  });

  beforeEach(() => {
    calls.generic.length = 0;
    calls.nbhd.length = 0;
    calls.refreshed.length = 0;
  });

  const fakeRects = () => ({ selectAll: () => ({ style: () => {} }) });

  const makeVizState = (raw_click) => ({
    model: { get: (key) => (key === 'update_trigger' ? raw_click : undefined) },
    cats: { cat: 'cluster' },
    seg: { version: 'default' },
    genes: { svg_bar_gene: fakeRects() },
    nbhd_cloud: {
      is_nbhd_cloud: true,
      selected_cluster_ids: new Set(),
      selected_gene: null,
      svg_bar_cluster: fakeRects(),
    },
    obs_store: {
      selected_cells: { set: () => {} },
      selected_genes: { set: () => {} },
      viz_nbhd_layer: { set: () => {} },
    },
    buttons: { buttons: { nbhd: { style: () => {} } } },
  });

  test('clicking a cell-cluster row selects the nbhd-cloud cluster, not the generic cell_layer path', async () => {
    const viz_state = makeVizState({
      type: 'row_label',
      value: { entity: 'cell', attr: 'leiden', name: '9' },
    });

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(calls.nbhd).toContain('set_nbhd_cloud_cluster_selection:9');
    expect(calls.nbhd).toContain('refresh_nbhd_cloud_cluster_cells');
    expect(calls.refreshed).toContain('nbhd_cloud_cell_layer');
    expect(calls.generic).not.toContain('update_selected_cats');
    expect(calls.refreshed).not.toContain('cell_layer');
  });

  test('clicking a gene row selects the nbhd-cloud gene, not the generic cell_layer path', async () => {
    const viz_state = makeVizState({
      type: 'row_label',
      value: { name: 'Matn1' },
    });

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(calls.nbhd).toContain('select_nbhd_cloud_gene:Matn1');
    expect(calls.refreshed).toContain('nbhd_cloud_shapes_layer');
    expect(calls.refreshed).toContain('nbhd_cloud_cell_layer');
    expect(calls.generic).not.toContain('update_cell_exp_array');
    expect(calls.refreshed).not.toContain('cell_layer');
  });

  test('clicking a cluster column selects the nbhd-cloud cluster, not the generic cell_layer path', async () => {
    const viz_state = makeVizState({
      type: 'col_label',
      value: { name: '9' },
    });

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(calls.nbhd).toContain('set_nbhd_cloud_cluster_selection:9');
    expect(calls.refreshed).not.toContain('cell_layer');
  });

  test('cutting a column dendrogram over several clusters selects all of them at once (meta-cluster)', async () => {
    const viz_state = makeVizState({
      type: 'col_dendro',
      value: {
        selected_names: ['3', '7', '9'],
        col_entity_full: { entity: 'cell', attr: 'leiden' },
      },
    });

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(calls.nbhd).toContain('set_nbhd_cloud_cluster_selection:3,7,9');
    expect(viz_state.nbhd_cloud.selected_cluster_ids).toEqual(
      new Set(['3', '7', '9'])
    );
    expect(calls.refreshed).not.toContain('cell_layer');
  });

  test('a plain Landscape/CellCloud viz_state (no nbhd_cloud) still takes the generic path', async () => {
    const viz_state = makeVizState({
      type: 'row_label',
      value: { name: 'Matn1' },
    });
    viz_state.nbhd_cloud = undefined;

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(calls.generic).toContain('update_cell_exp_array');
    expect(calls.refreshed).toContain('cell_layer');
    expect(calls.nbhd).toEqual([]);
  });
});
