/* global require */

const fs = require('fs');
const path = require('path');

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

const observable = (initial) => {
  let value = initial;
  return {
    get: () => value,
    set: jest.fn((next) => {
      value = next;
    }),
  };
};

const trxSource = fs
  .readFileSync(path.join(__dirname, '../ui/trx_handle.js'), 'utf8')
  .replace(/^export const /gm, 'const ');

describe.each([false, true])('viewport ordering (forced: %s)', (forced) => {
  let calc_viewport;
  let updatePaths;
  let updateTranscripts;
  let viz;
  let deck;
  let layers;

  const view = (x) => ({
    height: 10,
    width: 10,
    zoom: 0,
    target: [x, 0],
  });

  beforeEach(() => {
    updatePaths = jest.fn(async () => true);
    updateTranscripts = jest.fn(async () => {});
    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/core/calc_viewport.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    calc_viewport = new Function(
      'is_orbit_technology',
      'areBarDataEqual',
      'createEmptyCellCompact',
      'createEmptyTrxCompact',
      'makeVisibleTileKey',
      'visibleTiles',
      'update_path_layer_data',
      'update_trx_layer_data',
      'sync_trx_slider_range',
      'is_cluster_color_mode',
      `${trxSource}\n${source}\nreturn calc_viewport;`
    )(
      () => false,
      (a, b) => JSON.stringify(a) === JSON.stringify(b),
      () => ({ categoryIds: [] }),
      () => ({ geneIds: [] }),
      (tiles) => tiles.map(({ tileX }) => tileX).join(','),
      (minX) => [{ tileX: Math.round((minX + 5) / 100), tileY: 0 }],
      updatePaths,
      updateTranscripts,
      jest.fn(),
      () => true
    );
    viz = {
      img: { landscape_parameters: { tile_size: 100 } },
      genes: { gene_names: [], top_gene_counts: [] },
      cats: { cluster_counts: [] },
      combo_data: {},
      global_base_url: '/dataset',
      max_tiles_to_view: forced ? 1 : 5,
      trx_forced: forced,
      close_up: false,
      obs_store: {
        close_up: observable(false),
        deck_check: observable({ trx_data: true, path_data: true }),
        new_gene_bar_data: observable([]),
        new_cell_bar_data: observable([]),
      },
    };
    deck = { viewManager: { getViewports: () => [{}] } };
    layers = {};
  });

  test('a slow transcript fetch cannot start an obsolete segmentation load', async () => {
    const old = deferred();
    updateTranscripts.mockImplementationOnce(() => old.promise);
    const first = calc_viewport(view(0), deck, layers, viz);
    expect(viz.trx_loading).toBe(true);
    await calc_viewport(view(100), deck, layers, viz);
    expect(viz.viewport_cache.visibleTileKey).toBe('1');
    expect(viz.trx_loading).toBe(false);

    old.resolve();
    await first;
    expect(updatePaths).toHaveBeenCalledTimes(1);
    expect(updatePaths.mock.calls[0][1]).toEqual([{ tileX: 1, tileY: 0 }]);
    expect(viz.viewport_cache.visibleTileKey).toBe('1');
  });

  test('a late segmentation result cannot roll back the visible tile cache', async () => {
    const old = deferred();
    const started = deferred();
    updatePaths.mockImplementationOnce(() => {
      started.resolve();
      return old.promise;
    });
    const first = calc_viewport(view(0), deck, layers, viz);
    await started.promise;
    expect(viz.trx_loading).toBe(true);
    await calc_viewport(view(100), deck, layers, viz);
    old.resolve(true);
    await first;
    expect(viz.viewport_cache.visibleTileKey).toBe('1');
  });

  test('a failed segmentation load is retried for the same visible tiles', async () => {
    updatePaths.mockResolvedValueOnce(false);
    await calc_viewport(view(0), deck, layers, viz);
    expect(viz.viewport_cache.visibleTileKey).toBeNull();
    expect(viz.trx_loading).toBe(false);
    await calc_viewport(view(0), deck, layers, viz);
    expect(updatePaths).toHaveBeenCalledTimes(2);
    expect(viz.viewport_cache.visibleTileKey).toBe('0');
  });

  test('returning to the previous tiles reloads after another tile load fails', async () => {
    await calc_viewport(view(0), deck, layers, viz);
    updatePaths.mockResolvedValueOnce(false);
    await calc_viewport(view(100), deck, layers, viz);
    expect(viz.viewport_cache.visibleTileKey).toBeNull();

    await calc_viewport(view(0), deck, layers, viz);
    expect(updatePaths).toHaveBeenCalledTimes(3);
    expect(viz.viewport_cache.visibleTileKey).toBe('0');
  });

  test('returning to previous tiles during a pending load cannot leave readiness stuck', async () => {
    // Simulate the path updater's false→true readiness notifications.
    updatePaths.mockImplementation(async () => {
      viz.obs_store.deck_check.set({
        ...viz.obs_store.deck_check.get(),
        path_data: true,
      });
      return true;
    });
    await calc_viewport(view(0), deck, layers, viz);
    const pending = deferred();
    updateTranscripts.mockReturnValueOnce(pending.promise);
    const otherViewport = calc_viewport(view(100), deck, layers, viz);
    await calc_viewport(view(0), deck, layers, viz);

    pending.resolve();
    await otherViewport;
    expect(updatePaths).toHaveBeenCalledTimes(2);
    expect(viz.viewport_cache.visibleTileKey).toBe('0');
    expect(viz.obs_store.deck_check.get().path_data).toBe(true);
  });

  test('finalization stops a viewport waiting on tile data', async () => {
    const pending = deferred();
    updateTranscripts.mockReturnValueOnce(pending.promise);
    const first = calc_viewport(view(0), deck, layers, viz);
    viz.disposed = true;
    pending.resolve();
    await first;
    await calc_viewport(view(100), deck, layers, viz);
    expect(updatePaths).not.toHaveBeenCalled();
    expect(viz.viewport_cache.visibleTileKey).toBeNull();
  });

  test('an obsolete viewport cannot clear the current loading indicator', async () => {
    const old = deferred();
    const current = deferred();
    updateTranscripts
      .mockReturnValueOnce(old.promise)
      .mockReturnValueOnce(current.promise);
    const first = calc_viewport(view(0), deck, layers, viz);
    const second = calc_viewport(view(100), deck, layers, viz);

    old.resolve();
    await first;
    expect(viz.trx_loading).toBe(true);
    expect(updatePaths).not.toHaveBeenCalled();
    expect(viz.viewport_cache.visibleTileKey).toBeNull();

    current.resolve();
    await second;
    expect(viz.trx_loading).toBe(false);
    expect(updatePaths).toHaveBeenCalledTimes(1);
    expect(viz.viewport_cache.visibleTileKey).toBe('1');
  });
});
