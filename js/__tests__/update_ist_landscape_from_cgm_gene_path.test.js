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
        calls.selectedCats.push([...selected]);
        calls.events.push('selected-cats');
      };
      const update_selected_genes = () => {};
      const update_cell_exp_array = async (
        _cats, _genes, _baseUrl, gene, _version, _integer, _aws, cbgReader
      ) => {
        calls.expression.push({ gene, cbgReader });
        calls.events.push('expression');
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
    new Function('module', 'exports', 'calls', code)(
      module,
      module.exports,
      calls
    );
    ({ update_ist_landscape_from_cgm, sync_focused_gene_to_landscape } =
      module.exports);
  });

  beforeEach(() => {
    calls.events.length = 0;
    calls.expression.length = 0;
    calls.refreshed.length = 0;
    calls.selectedCats.length = 0;
  });

  const makeVizState = (selectedCells = []) => {
    let cells = selectedCells;
    const selectedCellSets = [];
    const cbgReader = { id: 'existing-cbg-reader' };

    return {
      selectedCellSets,
      cbgReader,
      model: {
        get: (key) =>
          key === 'update_trigger'
            ? {
                type: 'row_label',
                value: { entity: 'gene', attr: 'name', name: 'Matn1' },
              }
            : undefined,
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
        },
      ],
    ]);
    expect(model.save_changes).toHaveBeenCalledTimes(1);
  });
});
