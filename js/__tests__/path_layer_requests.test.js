/* global require */

const fs = require('fs');
const path = require('path');

const readSource = (relativePath) =>
  fs
    .readFileSync(path.join(__dirname, '..', relativePath), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const makeResult = (name) => ({
  paths: [
    [
      [1, 2],
      [3, 4],
      [1, 2],
    ],
  ],
  cellNames: [name],
});

const makeLayer = (data = [], props = { id: 'path-layer' }) => ({
  id: props.id,
  props: { ...props, data },
  data,
  clone: jest.fn((next) => makeLayer(next.data ?? data, { ...props, ...next })),
});

const makeState = () => ({
  global_base_url: 'https://example.test/dataset',
  seg: { version: 'default' },
  cats: { polygon_cell_names: ['original'] },
  viewport_request_id: 1,
  obs_store: {
    deck_check: {
      get: () => ({ path_data: false }),
      set: jest.fn(),
    },
  },
});

describe('segmentation path requests', () => {
  let fetchTiles;
  let updatePaths;
  let state;
  let layers;

  beforeEach(() => {
    fetchTiles = jest.fn();
    updatePaths = new Function(
      'grab_cell_tiles_in_view',
      'create_segmentation_error_handler',
      `${readSource('deck-gl/layers/path_layer.js')}\nreturn update_path_layer_data;`
    )(fetchTiles, () => jest.fn());
    state = makeState();
    layers = { path_layer: makeLayer(['original path']) };
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => jest.restoreAllMocks());

  const update = () =>
    updatePaths(state.global_base_url, [{ tileX: 1, tileY: 2 }], layers, state);

  test('tile changes rebuild path buffers and receive a fresh recovery handler', async () => {
    fetchTiles.mockResolvedValue(makeResult('cell'));
    await update();
    const first = layers.path_layer;
    await update();
    expect(layers.path_layer.id).not.toBe(first.id);
    expect(layers.path_layer.props.onError).not.toBe(first.props.onError);
  });

  test('an older fetch cannot overwrite newer geometry, names, or readiness', async () => {
    const oldFetch = deferred();
    const newFetch = deferred();
    const latest = makeResult('latest');
    fetchTiles
      .mockReturnValueOnce(oldFetch.promise)
      .mockReturnValueOnce(newFetch.promise);

    const oldRequest = update();
    const newRequest = update();
    state.obs_store.deck_check.set.mockImplementation(() => {
      expect(layers.path_layer.data).toBe(latest.paths);
      expect(state.cats.polygon_cell_names).toBe(latest.cellNames);
    });

    newFetch.resolve(latest);
    await expect(newRequest).resolves.toBe(true);
    const latestLayer = layers.path_layer;

    oldFetch.resolve(makeResult('stale'));
    await expect(oldRequest).resolves.toBe(false);
    expect(layers.path_layer).toBe(latestLayer);
    expect(state.cats.polygon_cell_names).toEqual(['latest']);
    expect(state.obs_store.deck_check.set).toHaveBeenCalledTimes(1);
  });

  test.each([
    ['a new viewport or zoom out', (s) => s.viewport_request_id++],
    ['a dataset change', (s) => (s.global_base_url = 'another-dataset')],
    ['a segmentation change', (s) => (s.seg.version = 'another-version')],
    ['widget disposal', (s) => (s.disposed = true)],
    ['reader disposal', (s) => (s.row_group_readers.cell.disposed = true)],
    ['reader replacement', (s) => (s.row_group_readers.cell = {})],
  ])('discards pending data after %s', async (_label, changeState) => {
    const pending = deferred();
    state.row_group_readers = { cell: { disposed: false } };
    fetchTiles.mockReturnValueOnce(pending.promise);
    const originalLayer = layers.path_layer;
    const request = update();

    changeState(state);
    pending.resolve(makeResult('stale'));

    await expect(request).resolves.toBe(false);
    expect(layers.path_layer).toBe(originalLayer);
    expect(state.cats.polygon_cell_names).toEqual(['original']);
    expect(state.obs_store.deck_check.set).not.toHaveBeenCalled();
  });

  test('ignores calls from a caller retaining an old dataset URL', async () => {
    await expect(updatePaths('old-dataset', [], layers, state)).resolves.toBe(
      false
    );
    expect(fetchTiles).not.toHaveBeenCalled();
  });

  test.each([
    ['a decoding failure', () => Promise.reject(new Error('bad geometry'))],
    ['mismatched cell names', () => ({ paths: [], cellNames: ['extra'] })],
  ])(
    'clears current geometry and names together after %s',
    async (_label, result) => {
      fetchTiles.mockImplementationOnce(result);
      await expect(update()).resolves.toBe(false);

      expect(layers.path_layer.data).toEqual([]);
      expect(state.cats.polygon_cell_names).toEqual([]);
      expect(state.obs_store.deck_check.set).toHaveBeenCalledWith({
        path_data: true,
      });
      expect(console.error).toHaveBeenCalledTimes(1);

      fetchTiles.mockResolvedValueOnce(makeResult('recovered'));
      await expect(update()).resolves.toBe(true);
      expect(state.cats.polygon_cell_names).toEqual(['recovered']);
    }
  );

  test('an old decoding failure cannot clear a successful newer layer', async () => {
    const pending = deferred();
    fetchTiles
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce(makeResult('latest'));
    const oldRequest = update();
    await update();

    pending.reject(new Error('stale invalid geometry'));
    await expect(oldRequest).resolves.toBe(false);
    expect(state.cats.polygon_cell_names).toEqual(['latest']);
    expect(layers.path_layer.data).toHaveLength(1);
    expect(state.obs_store.deck_check.set).toHaveBeenCalledTimes(1);
    expect(console.error).not.toHaveBeenCalled();
  });

  test('evicts cached tables on current failure while preserving caches on stale failure', async () => {
    const pending = deferred();
    const clearCellCache = jest.fn();
    const clearReaderCache = jest.fn();
    state.cache = { cell: { clear: clearCellCache } };
    state.row_group_readers = {
      cell: { requestCache: { clear: clearReaderCache } },
    };
    fetchTiles
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce(makeResult('latest'));

    const oldRequest = update();
    await update();
    pending.reject(new Error('stale invalid geometry'));
    await expect(oldRequest).resolves.toBe(false);
    expect(clearCellCache).not.toHaveBeenCalled();
    expect(clearReaderCache).not.toHaveBeenCalled();

    fetchTiles.mockRejectedValueOnce(new Error('current invalid geometry'));
    await expect(update()).resolves.toBe(false);
    expect(clearCellCache).toHaveBeenCalledTimes(1);
    expect(clearReaderCache).toHaveBeenCalledTimes(1);
  });
});

describe('cell tile result publication', () => {
  const makeFetcher = (fetchTables) =>
    new Function(
      'fetch_all_tables_new',
      'get_polygon_data',
      'concatenate_polygon_data',
      'extractPolygonPaths',
      'options',
      `${readSource('vector_tile/polygons/grab_cell_tiles_in_view.js')}\nreturn grab_cell_tiles_in_view;`
    )(
      fetchTables,
      (table) => table.paths,
      (tables) => tables.flat(),
      (paths) => paths,
      {}
    );

  const makeTable = () => ({
    getChild: () => ({ toArray: () => [1] }),
    paths: makeResult('unused').paths,
  });

  test.each([false, true])(
    'returns paired names and paths without mutation (row group mode: %s)',
    async (rowGroups) => {
      const pending = deferred();
      const fetchTables = jest.fn(() => pending.promise);
      const fetcher = makeFetcher(fetchTables);
      const state = {
        ...makeState(),
        use_row_groups: rowGroups,
        row_group_readers: { cell: { readTiles: () => pending.promise } },
        cache: { cell: {} },
        vector_name_integer: true,
      };
      state.cats.nameMapping_inv = { 1: 'original mapping' };
      const request = fetcher(state.global_base_url, [], state);
      state.cats.nameMapping_inv = { 1: 'replacement mapping' };
      const table = makeTable();
      pending.resolve(rowGroups ? table : [table]);

      await expect(request).resolves.toEqual({
        paths: table.paths,
        cellNames: ['original mapping'],
      });
      expect(state.cats.polygon_cell_names).toEqual(['original']);
    }
  );

  test.each([false, true])(
    'returns an empty paired result when no tables load (row groups: %s)',
    async (rowGroups) => {
      const fetcher = makeFetcher(async () => []);
      const state = {
        ...makeState(),
        use_row_groups: rowGroups,
        row_group_readers: { cell: { readTiles: async () => null } },
        cache: { cell: {} },
      };
      await expect(fetcher(state.global_base_url, [], state)).resolves.toEqual({
        paths: [],
        cellNames: [],
      });
      expect(state.cats.polygon_cell_names).toEqual(['original']);
    }
  );
});
