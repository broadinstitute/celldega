/* global require */

// The generic (Landscape / CellCloud) gene path in
// update_ist_landscape_from_cgm.js. Everything here is about *how many times*
// the cell layer gets rebuilt for one Clustergram gene click -- on a
// multi-million-cell CellCloud each rebuild walks every cell twice and
// re-uploads the position/color buffers to the GPU, so a duplicate is the
// difference between a responsive click and a visible stall.
//
// The reference is bar_plot.js's bar_callback_gene (the widget's own gene bar /
// search box), which does exactly one: guard deck.gl with deck_check, fetch,
// then a single update_selected_cats.
describe('update_ist_landscape_from_cgm gene path (Landscape / CellCloud)', () => {
  let update_ist_landscape_from_cgm;
  const calls = { generic: [], refreshed: [], deck_check: [] };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../widget_interactions/nbhd_cloud_link.js'),
      readStripped('../widget_interactions/update_ist_landscape_from_cgm.js'),
    ].join('\n');

    const shims = `
      const update_cat = (cats, cat) => { cats.cat = cat; };
      const update_selected_cats = (cats, selected) => {
        cats.selected_cats = selected;
        calls.generic.push('update_selected_cats:' + selected.join(','));
      };
      const update_selected_genes = (_genes, selected) => {
        calls.generic.push('update_selected_genes:' + selected.join(','));
      };
      const update_cell_exp_array = async (
        _cats, _genes, _base_url, gene, _version, _int, _aws, cbgReader
      ) => {
        calls.generic.push(
          'update_cell_exp_array:' + gene + ':cbg=' + (cbgReader ? cbgReader.id : 'none')
        );
        // Stand-in for a real failure mid-fetch (e.g. a gene missing from
        // meta_gene, which throws while reading its max).
        if (gene === 'ExplodingGene') {
          throw new Error('expression fetch failed');
        }
      };
      const handleAsyncError = (error) => { throw error; };
      const refresh_layer = (_viz_state, _layers_obj, name) => { calls.refreshed.push(name); };
      const select_nbhd_cloud_gene = async () => {};
      const set_nbhd_cloud_cluster_selection = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
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
    calls.refreshed.length = 0;
    calls.deck_check.length = 0;
  });

  // `selected_cells` here behaves like the real Observable: `set` always
  // notifies (it compares by identity, and every caller passes a fresh array),
  // and in the app that subscriber is what rebuilds the whole cell layer. The
  // recorded `set` calls are therefore a direct count of extra rebuilds.
  const makeVizState = (raw_click, { selected_cells = [] } = {}) => {
    let cells = selected_cells;
    const sets = [];
    return {
      sets,
      model: {
        get: (key) => (key === 'update_trigger' ? raw_click : undefined),
      },
      cats: { cat: 'cluster', selected_cats: [] },
      genes: {},
      seg: { version: 'default' },
      global_base_url: 'http://example.test',
      row_group_readers: { cbg: { id: 'cbg-reader' } },
      nbhd_cloud: { is_nbhd_cloud: false },
      obs_store: {
        selected_cells: {
          get: () => cells,
          set: (next) => {
            cells = next;
            sets.push(next);
          },
        },
        selected_genes: { set: () => {} },
        viz_nbhd_layer: { set: () => {} },
        deck_check: {
          get: () => ({ cell_layer: true, trx_layer: true }),
          set: (next) => calls.deck_check.push(next),
        },
      },
      buttons: { buttons: { nbhd: { style: () => {} } } },
    };
  };

  const geneRowClick = (name) => ({
    type: 'row_label',
    value: { name, entity: 'gene', attr: 'name' },
  });

  test('holds deck.gl back across the fetch instead of rendering stale expression', async () => {
    const viz_state = makeVizState(geneRowClick('Matn1'));

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    // The guard must be applied, and it must come before the fetch -- otherwise
    // the selected_genes subscriber's refresh lands while cell_exp_array still
    // holds the previous gene.
    expect(calls.deck_check[0]).toMatchObject({
      cell_layer: false,
      trx_layer: false,
    });
  });

  test('does not clear an already-empty cell selection (no duplicate layer rebuild)', async () => {
    const viz_state = makeVizState(geneRowClick('Matn1'));

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(viz_state.sets).toEqual([]);
    // Exactly one selection update reaches the layer, as in bar_callback_gene.
    expect(
      calls.generic.filter((c) => c.startsWith('update_selected_cats'))
    ).toEqual(['update_selected_cats:Matn1']);
  });

  test('still clears a real cell selection', async () => {
    const viz_state = makeVizState(geneRowClick('Matn1'), {
      selected_cells: ['cell_1', 'cell_2'],
    });

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(viz_state.sets).toEqual([[]]);
  });

  test('passes the CBG row-group reader on every gene path', async () => {
    const cases = [
      ['row label', geneRowClick('Matn1'), 'Matn1'],
      [
        'row dendrogram (single gene)',
        {
          type: 'row_dendro',
          value: {
            selected_names: ['Col2a1'],
            row_entity_full: { entity: 'gene', attr: 'name' },
          },
        },
        'Col2a1',
      ],
      [
        'gene x cluster matrix cell',
        {
          type: 'mat_value',
          value: {
            row: { name: 'Sox9' },
            col: { name: '7' },
            row_entity_full: { entity: 'gene', attr: 'name' },
            col_entity_full: { entity: 'cell', attr: 'leiden' },
          },
        },
        'Sox9',
      ],
      [
        'cluster x gene matrix cell',
        {
          type: 'mat_value',
          value: {
            row: { name: '7' },
            col: { name: 'Acan' },
            row_entity_full: { entity: 'cell', attr: 'leiden' },
            col_entity_full: { entity: 'gene', attr: 'name' },
          },
        },
        'Acan',
      ],
    ];

    for (const [label, raw_click, gene] of cases) {
      calls.generic.length = 0;
      const viz_state = makeVizState(raw_click);

      // eslint-disable-next-line no-await-in-loop
      await update_ist_landscape_from_cgm(null, {}, viz_state);

      // Without the reader these fall back to a per-gene cbg/<gene>.parquet
      // that a row-group dataset does not have -- a 404 that get_arrow_table
      // swallows, leaving the gene rendered with no expression at all.
      expect([label, calls.generic]).toEqual([
        label,
        expect.arrayContaining([
          `update_cell_exp_array:${gene}:cbg=cbg-reader`,
        ]),
      ]);
    }
  });

  test('releases the deck.gl guard when the expression fetch throws', async () => {
    const viz_state = makeVizState(geneRowClick('ExplodingGene'));

    // handleAsyncError is shimmed to rethrow, so a leak would surface here too.
    await expect(
      update_ist_landscape_from_cgm(null, {}, viz_state)
    ).rejects.toThrow('expression fetch failed');

    // Without this the widget is frozen: deck_ready never goes true again.
    expect(calls.deck_check.at(-1)).toMatchObject({
      cell_layer: true,
      trx_layer: true,
    });
  });

  test('a gene x cluster matrix cell filters the cells to that cluster', async () => {
    const viz_state = makeVizState({
      type: 'mat_value',
      value: {
        row: { name: 'Sox9' },
        col: { name: '7' },
        row_entity_full: { entity: 'gene', attr: 'name' },
        col_entity_full: { entity: 'cell', attr: 'leiden' },
      },
    });

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(viz_state.cats.cat).toBe('Sox9');
    expect(calls.generic).toContain('update_selected_cats:7');
  });

  test('re-clicking the active gene toggles back to cluster coloring', async () => {
    const viz_state = makeVizState(geneRowClick('Matn1'));
    viz_state.cats.cat = 'Matn1';

    await update_ist_landscape_from_cgm(null, {}, viz_state);

    expect(viz_state.cats.cat).toBe('cluster');
    expect(calls.generic).toContain('update_selected_cats:');
  });
});
