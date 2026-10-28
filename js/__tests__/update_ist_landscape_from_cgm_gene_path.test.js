/* global require */

describe('linked Clustergram gene selection for Landscape', () => {
  let update_ist_landscape_from_cgm;
  let sync_focused_gene_to_landscape;
  const calls = {
    events: [],
    expression: [],
    refreshed: [],
    selectedCats: [],
  };
  // When the expression load lands, and whether a newer load replaced it.
  const control = { applied: true, pending: null };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../global_variables/select_genes.js'),
      readStripped('../widget_interactions/nbhd_cloud_link.js'),
      readStripped('../widget_interactions/update_ist_landscape_from_cgm.js'),
    ].join('\n');

    const shims = `
      const update_cat = (cats, cat) => { cats.cat = cat; };
      // Like the real one: re-selecting the same array toggles it off.
      const update_selected_cats = (cats, selected) => {
        const same =
          selected.length === cats.selected_cats.length &&
          selected.every((value, i) => value === cats.selected_cats[i]);
        cats.selected_cats = same ? [] : selected;
        calls.selectedCats.push([...cats.selected_cats]);
        calls.events.push('selected-cats');
      };
      const force_set_selected_cats = (cats, selected) => {
        cats.selected_cats = selected;
        calls.selectedCats.push([...selected]);
        calls.events.push('selected-cats');
      };
      const update_selected_genes = () => {};
      const set_nbhd_button_color = () => {};
      const update_cell_exp_array = async (
        _cats, _genes, _baseUrl, gene, _version, _integer, _aws, cbgReader
      ) => {
        calls.expression.push({ gene, cbgReader });
        calls.events.push('expression');
        if (control.pending) await control.pending;
        return control.applied;
      };
      const handleAsyncError = (error) => { throw error; };
      const refresh_layer = (_vizState, _layersObj, name) => {
        calls.refreshed.push(name);
      };
      const select_nbhd_cloud_gene = async () => {};
      const set_nbhd_cloud_cluster_selection = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const sync_nbhd_cloud_opacity_sliders = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { update_ist_landscape_from_cgm, sync_focused_gene_to_landscape };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'calls', 'control', code)(
      module,
      module.exports,
      calls,
      control
    );
    ({ update_ist_landscape_from_cgm, sync_focused_gene_to_landscape } =
      module.exports);
  });

  beforeEach(() => {
    calls.events.length = 0;
    calls.expression.length = 0;
    calls.refreshed.length = 0;
    calls.selectedCats.length = 0;
    control.applied = true;
    control.pending = null;
  });

  const ROW_LABEL = {
    type: 'row_label',
    value: { entity: 'gene', attr: 'name', name: 'Matn1' },
  };

  const makeVizState = (selectedCells = [], trigger = ROW_LABEL) => {
    let cells = selectedCells;
    const selectedCellSets = [];
    const cbgReader = { id: 'existing-cbg-reader' };

    return {
      selectedCellSets,
      cbgReader,
      model: {
        get: (key) => (key === 'update_trigger' ? trigger : undefined),
      },
      cats: { cat: 'cluster', selected_cats: [] },
      genes: {},
      seg: { version: 'default' },
      global_base_url: 'http://example.test',
      row_group_readers: { cbg: cbgReader },
      nbhd_cloud: { is_nbhd_cloud: false },
      obs_store: {
        selected_cells: {
          get: () => cells,
          set: (next) => {
            cells = next;
            selectedCellSets.push(next);
            calls.events.push('selected-cells');
          },
        },
        viz_nbhd_layer: { set: () => {} },
      },
      buttons: { buttons: { nbhd: { style: () => {} } } },
    };
  };

  test('loads expression before the one canonical category-selection update', async () => {
    const vizState = makeVizState();

    await update_ist_landscape_from_cgm(null, {}, vizState);

    expect(calls.expression).toEqual([
      { gene: 'Matn1', cbgReader: vizState.cbgReader },
    ]);
    expect(calls.selectedCats).toEqual([['Matn1']]);
    expect(calls.events).toEqual(['expression', 'selected-cats']);
  });

  test('does not notify selected_cells when it is already empty', async () => {
    const vizState = makeVizState();

    await update_ist_landscape_from_cgm(null, {}, vizState);

    expect(vizState.selectedCellSets).toEqual([]);
  });

  test('still clears a real individual-cell selection', async () => {
    const vizState = makeVizState(['cell-1', 'cell-2']);

    await update_ist_landscape_from_cgm(null, {}, vizState);

    expect(vizState.selectedCellSets).toEqual([[]]);
    expect(calls.events).toEqual([
      'expression',
      'selected-cells',
      'selected-cats',
    ]);
  });

  test('does not explicitly refresh layers already owned by subscriptions', async () => {
    const vizState = makeVizState();

    await update_ist_landscape_from_cgm(null, {}, vizState);

    expect(calls.refreshed).toEqual([]);
  });

  const hold_expression = () => {
    let release;
    control.pending = new Promise((resolve) => {
      release = resolve;
    });
    return () => release();
  };

  // What a cluster bar click does (bar_callback_cat): no expression load.
  const click_cluster = (vizState, cluster) => {
    vizState.cats.cat = 'cluster';
    vizState.cats.selected_cats = [cluster];
  };

  test('leaves a cluster clicked while the gene loads selected', async () => {
    const vizState = makeVizState();
    const release = hold_expression();
    const update = update_ist_landscape_from_cgm(null, {}, vizState);

    click_cluster(vizState, '3');
    release();
    await update;
    expect(calls.selectedCats).toEqual([]);
    expect(vizState.cats).toMatchObject({
      cat: 'cluster',
      selected_cats: ['3'],
    });
  });

  test('leaves the selection to a newer gene load', async () => {
    const vizState = makeVizState();
    control.applied = false;

    await update_ist_landscape_from_cgm(null, {}, vizState);
    expect(calls.selectedCats).toEqual([]);
  });

  test('clears the shown gene without loading its expression', async () => {
    const vizState = makeVizState();
    vizState.cats.cat = 'Matn1';

    await update_ist_landscape_from_cgm(null, {}, vizState);
    expect(calls.expression).toEqual([]);
    expect(calls.selectedCats).toEqual([[]]);
    expect(vizState.cats.cat).toBe('cluster');
  });

  test('a gene x cluster matrix click yields to a cluster clicked meanwhile', async () => {
    const vizState = makeVizState([], {
      type: 'mat_value',
      value: {
        row: { entity: 'gene', attr: 'name', name: 'Matn1' },
        col: { entity: 'cell', attr: 'leiden', name: '5' },
      },
    });
    vizState.obs_store.selected_cells.set = () => {};

    // Without a newer click, the gene's cells in the cluster are shown.
    await update_ist_landscape_from_cgm(null, {}, vizState);
    expect(calls.selectedCats).toEqual([['5']]);

    calls.selectedCats.length = 0;
    const release = hold_expression();
    const update = update_ist_landscape_from_cgm(null, {}, vizState);
    click_cluster(vizState, '3');
    release();
    await update;
    expect(calls.selectedCats).toEqual([]);
    expect(vizState.cats.selected_cats).toEqual(['3']);
  });

  test('an Enrich gene click loads that gene through an AnnData Zarr reader', async () => {
    const values = { focused_gene: 'CD3E', update_trigger: null };
    const zarr_reader = { readGeneExpression: async () => ({}) };
    const vizState = makeVizState();
    vizState.row_group_readers = { cbg: zarr_reader };
    vizState.model = {
      get: (key) => values[key],
      set: (key, value) => {
        values[key] = value;
      },
      save_changes: () => {},
    };

    sync_focused_gene_to_landscape(vizState.model);
    await update_ist_landscape_from_cgm(null, {}, vizState);

    expect(calls.expression).toEqual([
      { gene: 'CD3E', cbgReader: zarr_reader },
    ]);
    expect(calls.selectedCats).toEqual([['CD3E']]);

    // A second view of the same Landscape handles the same focus: the gene
    // stays shown instead of toggling off.
    await update_ist_landscape_from_cgm(null, {}, vizState);
    expect(vizState.cats.cat).toBe('CD3E');
    expect(vizState.cats.selected_cats).toEqual(['CD3E']);
  });

  test('a repeated Clustergram row click still toggles its gene off', async () => {
    const vizState = makeVizState();
    await update_ist_landscape_from_cgm(null, {}, vizState);
    await update_ist_landscape_from_cgm(null, {}, vizState);
    expect(vizState.cats.cat).toBe('cluster');
    expect(vizState.cats.selected_cats).toEqual([]);
  });

  test('turns a browser-linked Enrich focus into a Landscape gene update', () => {
    const values = {
      focused_gene: 'GATA3',
      update_trigger: { type: 'old' },
    };
    const changes = [];
    const model = {
      get: (key) => values[key],
      set: (key, value) => {
        values[key] = value;
        changes.push([key, value]);
      },
      save_changes: jest.fn(),
    };

    expect(sync_focused_gene_to_landscape(model)).toBe(true);
    expect(changes).toEqual([
      ['update_trigger', null],
      [
        'update_trigger',
        {
          type: 'row_label',
          value: {
            name: 'GATA3',
            entity: 'gene',
            attr: 'name',
            row_entity: 'gene',
          },
          focus: true,
        },
      ],
    ]);
    expect(model.save_changes).toHaveBeenCalledTimes(1);
  });
});
