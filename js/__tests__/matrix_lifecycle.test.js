/* global require */

const fs = require('fs');
const path = require('path');

const read = (name) =>
  fs.readFileSync(path.join(__dirname, '..', name), 'utf8');
const create_clustergram_store = new Function(
  `${read('obs_store/clustergram_store.js').replace('export const', 'const')}; return create_clustergram_store;`
)();
const ManualCategoryStore = new Function(
  `${read('obs_store/manual_category_store.js').replace('export class', 'class')}; return ManualCategoryStore;`
)();

describe('Matrix lifecycle', () => {
  let matrix_viz;
  let states;
  let decks;
  let model;
  let listeners;
  let dependencies;
  let values;

  beforeEach(() => {
    jest.useFakeTimers();
    states = [];
    decks = [];
    values = {};
    listeners = new Map();
    model = {
      get: (name) => values[name],
      set: jest.fn((name, value) => {
        values[name] = value;
      }),
      save_changes: jest.fn(),
      on: jest.fn((event, callback) => {
        if (!listeners.has(event)) listeners.set(event, new Set());
        listeners.get(event).add(callback);
      }),
      off: jest.fn((event, callback) => listeners.get(event)?.delete(callback)),
    };
    const source = read('viz/matrix_viz.js');
    dependencies = {};
    for (const match of source.matchAll(
      /^import\s*{([^}]+)}\s*from\s*['"][^'"]+['"];$/gm
    )) {
      match[1]
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .forEach((name) => {
          dependencies[name] = jest.fn();
        });
    }
    Object.assign(dependencies, {
      ini_deck: () => {
        const deck = { setProps: jest.fn(), finalize: jest.fn() };
        decks.push(deck);
        return deck;
      },
      set_mat_constants: (instance_model, _network, root) => {
        const state = {
          model: instance_model,
          root,
          row_nodes: [{ name: 'G' }],
          col_nodes: [{ name: 'C' }],
          mat: { viz_mode: 'heatmap', net_mat: [[42]] },
          attr: {},
          dendro: {},
          zoom: {},
          crop: {},
          views: { views_list: [] },
          obs_store: {
            ...create_clustergram_store(),
            manual_cat: {
              row: new ManualCategoryStore('row'),
              col: new ManualCategoryStore('col'),
            },
          },
        };
        states.push(state);
        return state;
      },
      make_matrix_ui_container: () => document.createElement('div'),
      buildCellSlice: (row, col, value) => ({ row, col, value }),
    });
    matrix_viz = new Function(
      ...Object.keys(dependencies),
      `${source
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ')}; return matrix_viz;`
    )(...Object.values(dependencies));
  });
  afterEach(() => jest.useRealTimers());

  test('supports the minimal model used by the standalone JavaScript API', async () => {
    model.on = () => {};
    delete model.off;
    const matrix = await matrix_viz(model, document.createElement('div'), {});
    expect(() => matrix.finalize()).not.toThrow();
    expect(decks[0].finalize).toHaveBeenCalledTimes(1);
  });

  test('replacement unregisters only its own listeners, including matrix-slice requests', async () => {
    const outside = jest.fn();
    model.on('change:matrix_slice_request', outside);
    const firstElement = document.createElement('div');
    const first = await matrix_viz(model, firstElement, {});
    const stale = [...listeners.get('change:matrix_slice_request')][1];
    const secondElement = document.createElement('div');
    const second = await matrix_viz(model, secondElement, {});
    first.finalize();
    first.finalize();
    expect(decks[0].finalize).toHaveBeenCalledTimes(1);
    expect(firstElement.childElementCount).toBe(0);
    expect(secondElement.childElementCount).toBe(2);
    // All model events now have just the live Matrix listener (and our external one).
    for (const [event, callbacks] of listeners) {
      expect(callbacks.size).toBe(
        event === 'change:matrix_slice_request' ? 2 : 1
      );
    }
    values.matrix_slice_request = {
      req_id: 'slice',
      op: 'cell',
      row: 0,
      col: 0,
    };
    model.set.mockClear();
    stale();
    expect(model.set).not.toHaveBeenCalled();
    listeners
      .get('change:matrix_slice_request')
      .forEach((callback) => callback());
    expect(outside).toHaveBeenCalledTimes(1);
    expect(model.set).toHaveBeenCalledTimes(2);
    expect(values.matrix_slice_result).toEqual({
      req_id: 'slice',
      row: 0,
      col: 0,
      value: 42,
    });
    second.finalize();
    expect(listeners.get('change:matrix_slice_request')).toEqual(
      new Set([outside])
    );
    for (const [event, callbacks] of listeners) {
      if (event !== 'change:matrix_slice_request')
        expect(callbacks.size).toBe(0);
    }
  });

  test('finalize cancels delayed interactions, subscriptions, and DOM listeners', async () => {
    const element = document.createElement('div');
    const matrix = await matrix_viz(model, element, {});
    const state = states[0];
    const late = jest.fn();
    const timer = () => setTimeout(late, 150);
    state.labels.click_timeouts = { row: timer(), col: timer() };
    state.labels.attr_click_timeouts = { row: timer(), col: timer() };
    state.labels._attr_refresh_timer = timer();
    state.dendro.click_timeouts = { row: timer(), col: timer() };
    state.dendro._hover_timer = timer();
    state.mat._comp_hover_timer = timer();
    state.mat._comp_hover_col_timer = timer();
    state._cat_hover_timer = timer();
    state.crop._snap_timer = timer();
    state.zoom._programmatic_transition_timer = timer();
    state.dendro._native_click_handler = late;
    state.dendro._native_pointerdown_handler = late;
    state.root.addEventListener('click', late, true);
    state.root.addEventListener('pointerdown', late, true);
    state.obs_store.selected_genes.subscribe(late, { immediate: false });
    state.obs_store.manual_cat.row.subscribe(late, { immediate: false });
    state.attr.editor = { destroy: jest.fn() };
    state.gene_info_box = { clear: jest.fn() };
    matrix.finalize();
    jest.runAllTimers();
    state.root.dispatchEvent(new Event('click'));
    state.root.dispatchEvent(new Event('pointerdown'));
    state.root.dispatchEvent(new Event('pointerleave'));
    state.obs_store.selected_genes.set(['NEW']);
    state.obs_store.manual_cat.row.setAttribute('new attribute');
    expect(late).not.toHaveBeenCalled();
    expect(dependencies.clear_dendro_hover).not.toHaveBeenCalled();
    expect(state.attr.editor.destroy).toHaveBeenCalledTimes(1);
    expect(state.gene_info_box.clear).toHaveBeenCalledTimes(1);
  });
});
