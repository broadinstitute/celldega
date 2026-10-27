/* global require */

const fs = require('fs');
const path = require('path');

const readSource = (relativePath) =>
  fs
    .readFileSync(path.join(__dirname, '..', relativePath), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const refreshLayer = new Function(
  `${readSource('utils/refresh_layer.js')}\nreturn refresh_layer;`
)();

const makeLayer = (props) => ({
  id: props.id,
  props,
  clone: jest.fn((updates) => makeLayer({ ...props, ...updates })),
});

describe('segmentation renderer recovery', () => {
  let state;
  let onError;
  let original;
  let microtasks;

  beforeEach(() => {
    microtasks = [];
    const createHandler = new Function(
      'refresh_layer',
      'queueMicrotask',
      `${readSource('deck-gl/layers/segmentation_recovery.js')}\nreturn create_segmentation_error_handler;`
    )(refreshLayer, (callback) => microtasks.push(callback));
    let flags = { path_layer: true, path_data: true };
    state = {
      global_base_url: 'https://example.test/dataset',
      seg: { version: 'default' },
      cats: { polygon_cell_names: ['cell'] },
      obs_store: {
        deck_check: {
          get: () => flags,
          set: jest.fn((nextFlags) => (flags = nextFlags)),
        },
      },
    };
    onError = createHandler(state);
    original = makeLayer({
      id: 'path-layer',
      data: [
        [
          [1, 2],
          [3, 4],
          [1, 2],
        ],
      ],
      visible: true,
      getColor: jest.fn(),
      onError,
    });
    state.layers_obj = { path_layer: original };
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => jest.restoreAllMocks());

  const flushMicrotasks = () => {
    while (microtasks.length) microtasks.shift()();
  };

  test('rebuilds once outside the render cycle and preserves geometry and cell IDs', () => {
    const error = new Error('attribute upload failed');
    expect(onError(error)).toBe(true);
    expect(state.layers_obj.path_layer).toBe(original);
    expect(state.obs_store.deck_check.set).not.toHaveBeenCalled();
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining('[segmentation]'),
      expect.objectContaining({
        datasetUrl: state.global_base_url,
        segmentationVersion: 'default',
        pathCount: 1,
        layerId: 'path-layer',
        error,
      })
    );

    flushMicrotasks();
    const recovered = state.layers_obj.path_layer;
    expect(recovered.id).toMatch(/^path-layer-recovery-\d+$/);
    expect(recovered.props.data).toBe(original.props.data);
    expect(recovered.props.onError).toBe(onError);
    expect(state.cats.polygon_cell_names).toEqual(['cell']);
    expect(state.obs_store.deck_check.set.mock.calls).toEqual([
      [{ path_layer: false, path_data: true }],
      [{ path_layer: true, path_data: true }],
    ]);
  });

  test('uses the latest visibility and selection props on a matching clone', () => {
    onError(new Error('update failed'));
    const getColor = jest.fn();
    const latest = original.clone({ visible: false, getColor });
    state.layers_obj.path_layer = latest;

    flushMicrotasks();
    expect(latest.clone).toHaveBeenCalledTimes(1);
    expect(state.layers_obj.path_layer.props).toMatchObject({
      visible: false,
      getColor,
    });
  });

  test('coalesces pending errors and delegates after the single retry', () => {
    expect(onError(new Error('first'))).toBe(true);
    expect(onError(new Error('while pending'))).toBe(true);
    expect(microtasks).toHaveLength(1);
    flushMicrotasks();

    const recovered = state.layers_obj.path_layer;
    expect(onError(new Error('retry also failed'))).toBe(false);
    expect(microtasks).toHaveLength(0);
    expect(state.layers_obj.path_layer).toBe(recovered);
    expect(original.clone).toHaveBeenCalledTimes(1);
  });

  test.each([
    ['disposal', (s) => (s.disposed = true)],
    [
      'new data',
      (s) => (s.layers_obj.path_layer = original.clone({ data: [] })),
    ],
    [
      'new layer ID',
      (s) => (s.layers_obj.path_layer = original.clone({ id: 'new' })),
    ],
    [
      'new error handler',
      (s) =>
        (s.layers_obj.path_layer = original.clone({ onError: () => false })),
    ],
    ['new dataset', (s) => (s.global_base_url = 'https://example.test/next')],
    ['new segmentation', (s) => (s.seg.version = 'updated')],
  ])('discards pending recovery after %s', (_label, changeState) => {
    onError(new Error('update failed'));
    changeState(state);
    const latest = state.layers_obj.path_layer;

    flushMicrotasks();
    expect(state.layers_obj.path_layer).toBe(latest);
    expect(state.obs_store.deck_check.set).not.toHaveBeenCalled();
  });

  test('ignores stale callbacks or errors after widget disposal', () => {
    state.disposed = true;
    expect(onError(new Error('disposed'))).toBe(false);
    state.disposed = false;
    state.layers_obj.path_layer = original.clone({ onError: () => false });
    expect(onError(new Error('old layer'))).toBe(false);
    expect(microtasks).toHaveLength(0);
  });
});
