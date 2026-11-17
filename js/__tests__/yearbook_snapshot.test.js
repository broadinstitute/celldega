/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../viz/yearbook_snapshot.js'), 'utf8')
  .replace(/import[\s\S]*?from ['"][^'"]+['"];\n/g, '')
  .replace(
    'export const create_yearbook_snapshot_api',
    'const create_yearbook_snapshot_api'
  );

const setup = () => {
  const display = {
    space: 'spatial',
    view: { zoom: 9 },
    genes: ['G1'],
    layers: { image: true },
    selected_cells: [],
  };
  const apply = jest.fn(async () => []);
  const make = new Function(
    'capture_deck',
    'apply_landscape_state',
    'get_landscape_replay_state',
    'create_snapshot_api',
    'landscape_identity',
    'landscape_source',
    'wait_for_canvas',
    'wait_for_operation',
    `${source}; return create_yearbook_snapshot_api;`
  )(
    jest.fn(() => ({ png: 'UE5H' })),
    apply,
    () => ({ ...display }),
    (api) => api,
    () => ({ cells: { count: 3 } }),
    () => ({ base_url: 'data' }),
    async () => {},
    (op) => op()
  );
  const state = {
    yearbook: {
      cells: ['c1', 'c2', 'c3'],
      current_page: 0,
      zoom_level: 2,
      query: { gene: 'G1' },
      num_rows: 1,
      num_cols: 2,
      portrait_size_um: 50,
      portrait_gap: 4,
    },
    cats: {
      cell_name_to_index_map: new Map([
        ['c1', 0],
        ['c2', 1],
        ['c3', 2],
      ]),
    },
    model: { set: jest.fn(), save_changes: jest.fn() },
  };
  const refresh = jest.fn(async () => {});
  const selection = {
    get_selected_cells: () => ['c2'],
    set_selected_cells: jest.fn(),
  };
  const api = make({
    state,
    deck: { getCanvas: () => ({ clientWidth: 400, clientHeight: 200 }) },
    layers: {},
    refresh,
    selection,
    ready: async () => {},
  });
  return { api, state, refresh, selection, apply };
};

test('Yearbook captures ordered portraits, grid identity, page, zoom and selections', () => {
  const { api } = setup();
  expect(api.kind).toBe('yearbook');
  expect(api.get_replay_state()).toEqual({
    cells: ['c1', 'c2', 'c3'],
    page: 0,
    zoom: 2,
    query: { gene: 'G1' },
    selected_cells: ['c2'],
    display: { genes: ['G1'], layers: { image: true } },
  });
  expect(api.identity().grid).toEqual({ rows: 1, cols: 2, size: 50, gap: 4 });
  expect(api.source().widget).toBe('Yearbook');
});

test('restores captured order without rerunning a query and waits for refresh', async () => {
  const { api, state, refresh, selection, apply } = setup();
  const saved = {
    ...api.get_replay_state(),
    cells: ['c3', 'c1', 'c2'],
    page: 1,
    zoom: 4,
  };
  await api.apply_state(saved);
  expect(state.yearbook.cells).toEqual(['c3', 'c1', 'c2']);
  expect(state.yearbook.current_page).toBe(1);
  expect(state.yearbook.zoom_level).toBe(4);
  expect(apply).toHaveBeenCalledWith(state, expect.any(Object), saved.display);
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(selection.set_selected_cells).toHaveBeenCalledWith(['c2']);
  expect(state.yearbook.restoring).toBe(false);
});

test.each([
  { cells: ['missing'] },
  { page: 99 },
  { zoom: NaN },
  { display: { view: {} } },
])('invalid replay fails before mutations: %j', async (invalid) => {
  const { api, state, refresh, apply } = setup();
  await expect(
    api.apply_state({ ...api.get_replay_state(), ...invalid })
  ).rejects.toThrow();
  expect(state.yearbook.cells).toEqual(['c1', 'c2', 'c3']);
  expect(apply).not.toHaveBeenCalled();
  expect(refresh).not.toHaveBeenCalled();
});

test('a failed load releases the model sync guard', async () => {
  const { api, state, refresh } = setup();
  refresh.mockRejectedValue(new Error('tile unavailable'));
  await expect(api.apply_state(api.get_replay_state())).rejects.toThrow(
    'tile unavailable'
  );
  expect(state.yearbook.restoring).toBe(false);
});
