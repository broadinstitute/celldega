/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const get_composition_layout = jest.fn();
const rightmost_composition_col = jest.fn();
const empty_dendro_tree_data = () => ({
  background: [],
  row_branches: [],
  col_branches: [],
  water: [],
  cut_outline: [],
  cut: [],
  caption: [],
});
const remove_dendro_tree_layers = jest.fn((layers) => {
  delete layers.preview;
});
const update_dendro_tree_layers = jest.fn((layers, data, options) => {
  layers.preview = { data, options };
});
const get_mat_layers_list = (layers) => Object.values(layers);
const preview_views = [
  'dendro_tree_backdrop',
  'dendro_tree_rows',
  'dendro_tree_cols',
  'dendro_tree_foreground',
];
const without_dendro_tree_views = (views) =>
  views.filter((view) => !preview_views.includes(view.id));
const with_dendro_tree_views = (views) => [
  ...without_dendro_tree_views(views),
  ...preview_views.map((id) => ({ id })),
];
const initialize_dendro_tree_overlay = new Function(
  'get_composition_layout',
  'rightmost_composition_col',
  'empty_dendro_tree_data',
  'remove_dendro_tree_layers',
  'update_dendro_tree_layers',
  'get_mat_layers_list',
  'with_dendro_tree_views',
  'without_dendro_tree_views',
  `
  ${read('matrix/crop_filter.js')}
  ${read('matrix/dendro_tree.js')}
  ${read('ui/dendro_tree_overlay.js')}
  return initialize_dendro_tree_overlay;
`
)(
  get_composition_layout,
  rightmost_composition_col,
  empty_dendro_tree_data,
  remove_dendro_tree_layers,
  update_dendro_tree_layers,
  get_mat_layers_list,
  with_dendro_tree_views,
  without_dendro_tree_views
);

describe('deck.gl temporary dendrogram tree preview', () => {
  let state;
  let controller;
  let deck;
  let layers;
  const event = (target, type) =>
    target.dispatchEvent(new Event(type, { bubbles: true }));

  beforeEach(() => {
    jest.useFakeTimers();
    update_dendro_tree_layers.mockClear();
    remove_dendro_tree_layers.mockClear();
    get_composition_layout.mockReset();
    rightmost_composition_col.mockReset();
    const el = document.createElement('div');
    const root = document.createElement('div');
    const row = document.createElement('input');
    const col = document.createElement('input');
    el.append(row, col, root);
    document.body.append(el);
    state = {
      el,
      root,
      views: { views_list: [{ id: 'matrix' }] },
      order: { current: { row: 'clust', col: 'clust' } },
      crop: { filter: { row: null, col: null } },
      mat: {
        num_rows: 2,
        num_cols: 2,
        viz_mode: 'heatmap',
        orders: { row: { clust: [2, 1] }, col: { clust: [2, 1] } },
      },
      row_nodes: [{ group_links: 0 }, { group_links: 1 }],
      col_nodes: [{ group_links: 0 }, { group_links: 1 }],
      linkage: { row: [[0, 1, 1, 2]], col: [[0, 1, 1, 2]] },
      viz: {
        mat_width: 300,
        mat_height: 200,
        row_offset: 100,
        col_offset: 150,
      },
      dendro: {
        max_linkage_dist: { row: 1.01, col: 1.01 },
        sliders: { row, col, row_percent: 50, col_percent: 50 },
      },
    };
    deck = { setProps: jest.fn() };
    layers = {};
    controller = initialize_dendro_tree_overlay(state, deck, layers);
  });

  afterEach(() => {
    controller.destroy();
    state.el.remove();
    jest.useRealTimers();
  });

  test('renders every visual as deck layer data in the existing scene', () => {
    event(state.dendro.sliders.col, 'pointerdown');
    const { data } = layers.preview;
    expect(state.root.querySelector('canvas')).toBeNull();
    expect(state.root.querySelector('.dendro-tree-overlay')).toBeNull();
    expect(state.views.views_list.map((view) => view.id)).toEqual([
      'matrix',
      ...preview_views,
    ]);
    expect(data.background).toHaveLength(1);
    expect(data.col_branches).toHaveLength(1);
    expect(data.row_branches).toHaveLength(0);
    expect(data.water).toHaveLength(1);
    expect(data.cut_outline[0].width).toBe(5);
    expect(data.cut[0].width).toBe(2.5);
    expect(data.caption[0].text).toContain('Column tree · 2 groups');
  });

  test('keeps branch leaf coordinates in matrix world space and water screen-fitted', () => {
    controller.show('row');
    let { data } = layers.preview;
    expect(data.row_branches[0].path[0]).toEqual([296, 150]);
    expect(data.row_branches[0].path[3]).toEqual([296, 250]);
    expect(data.water[0].polygon).toEqual([
      [296, 4],
      [296, 196],
      [150, 196],
      [150, 4],
    ]);

    controller.show('col');
    ({ data } = layers.preview);
    expect(data.col_branches[0].path[0]).toEqual([75, 196]);
    expect(data.col_branches[0].path[3]).toEqual([225, 196]);
    expect(data.water[0].polygon[0]).toEqual([4, 196]);
    expect(data.water[0].polygon[2][1]).toBeCloseTo(100);
  });

  test('uses reduced RANK leaf slots mapped back to full matrix rows', () => {
    state.mat.num_rows = 4;
    state.viz.row_offset = 50;
    state.row_nodes = Array.from({ length: 4 }, (_, i) => ({ group_links: i }));
    state.mat.orders.row.clust = [0, 1, 0, 2];
    state.rank_view = {
      leaf_map: { row: [1, 3] },
      filter: { row: [1, 3], col: null },
    };
    controller.show('row');
    const path_data = layers.preview.data.row_branches[0].path;
    expect(path_data[0][1]).toBe(250);
    expect(path_data[3][1]).toBe(150);
  });

  test('composition rows use nonuniform rightmost-bar positions', () => {
    state.mat.viz_mode = 'composition';
    state.mat.num_rows = 3;
    state.mat.orders.row.clust = [3, 2, 1];
    state.row_nodes.push({ group_links: 2 });
    state.linkage.row = [
      [0, 1, 0.5, 2],
      [3, 2, 1, 3],
    ];
    rightmost_composition_col.mockReturnValue(1);
    get_composition_layout.mockReturnValue({
      '0_1': { position: [225, 270] },
      '1_1': { position: [225, 150] },
      '2_1': { position: [225, 120] },
    });
    controller.show('row');
    const branches = layers.preview.data.row_branches;
    expect(branches[0].path[0][1]).toBe(270);
    expect(branches[0].path[3][1]).toBe(150);
    expect(branches[1].path[0][1]).toBe(210);
    expect(branches[1].path[3][1]).toBe(120);
  });

  test('slider changes refresh groups and preserve release/fade timing', () => {
    event(state.dendro.sliders.col, 'pointerdown');
    state.dendro.sliders.col_percent = 100;
    state.col_nodes.forEach((node) => {
      node.group_links = 2;
    });
    event(state.dendro.sliders.col, 'input');
    expect(layers.preview.data.caption[0].text).toContain('1 group');
    expect(state.dendro.sliders.col.getAttribute('aria-valuetext')).toBe(
      '100% — 1 group'
    );
    jest.advanceTimersByTime(1000);
    expect(controller.has_views()).toBe(true);
    event(window, 'pointerup');
    jest.advanceTimersByTime(449);
    expect(layers.preview.options.opacity).toBe(1);
    jest.advanceTimersByTime(1);
    expect(layers.preview.options).toMatchObject({ opacity: 0, duration: 180 });
    jest.advanceTimersByTime(180);
    expect(controller.has_views()).toBe(false);
  });

  test('camera activity cannot reopen a hidden preview or reset its timer', () => {
    event(state.dendro.sliders.row, 'pointerdown');
    event(window, 'pointerup');
    const calls = update_dendro_tree_layers.mock.calls.length;
    jest.advanceTimersByTime(450 + 180);
    expect(controller.has_views()).toBe(false);
    expect(update_dendro_tree_layers.mock.calls.length).toBe(calls + 2);
    deck.setProps({ viewState: { matrix: { zoom: [2, 3] } } });
    jest.advanceTimersByTime(1000);
    expect(controller.has_views()).toBe(false);
    expect(update_dendro_tree_layers.mock.calls.length).toBe(calls + 2);
  });

  test('invalid modes hide immediately and destroy removes state/listeners', () => {
    controller.show('row');
    state.order.current.row = 'rank';
    controller.refresh();
    expect(controller.has_views()).toBe(false);
    controller.destroy();
    controller.destroy();
    expect(remove_dendro_tree_layers).toHaveBeenCalledTimes(1);
    event(state.dendro.sliders.row, 'input');
    jest.runAllTimers();
    expect(controller.has_views()).toBe(false);
    expect(jest.getTimerCount()).toBe(0);
  });
});
