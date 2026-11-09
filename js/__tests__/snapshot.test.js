/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../viz/snapshot.js'), 'utf8')
  .replace(/^import .*;$/gm, 'const CELLDEGA_VERSION = "test";')
  .replace(/^export const /gm, 'const ');
const { create_snapshot_api, handle_snapshot_message, wait_for_operation } =
  new Function(
    'globalThis',
    'TextEncoder',
    `${source}; return { create_snapshot_api, handle_snapshot_message, wait_for_operation };`
  )({ crypto: require('crypto').webcrypto }, require('util').TextEncoder);

const fixture = (overrides = {}) => {
  const data = { cells: ['a', 'b'], values: [1, 2] };
  let position = 1;
  const dimensions = { width: 500, height: 400 };
  const unverified = [];
  const apply = jest.fn(async (state) => {
    position = state.view.target[0];
    return ['moved'];
  });
  const api = create_snapshot_api({
    kind: 'clustergram',
    get_state: () => ({
      kind: 'clustergram',
      view: { target: [position, 0], zoom: [0, 0] },
    }),
    capture_raster: () => ({
      png: `frame-${position}`,
      width: 500,
      height: 400,
    }),
    apply_state: apply,
    identity: () => ({ data, coverage: 'matrix-content', unverified }),
    viewport: () => dimensions,
    ...overrides,
  });
  return {
    api,
    data,
    dimensions,
    apply,
    unverified,
    move: (x) => {
      position = x;
    },
  };
};

test('image, observations and identity are frozen before asynchronous hashing', async () => {
  const f = fixture();
  const pending = f.api.snapshot();
  f.move(9);
  f.data.values[0] = 99;
  const snapshot = await pending;
  expect(snapshot.image.png).toBe('frame-1');
  expect(snapshot.observed_state.view.target).toEqual([1, 0]);
  expect(snapshot.state.view.target).toEqual([1, 0]);
  const fresh = fixture();
  await fresh.api.restore_snapshot(JSON.parse(JSON.stringify(snapshot)));
  expect(fresh.apply).toHaveBeenCalledWith(snapshot.state);
  await expect(f.api.restore_snapshot(snapshot)).rejects.toThrow('fingerprint');
  expect(f.apply).not.toHaveBeenCalled();
});

test('bounded observations do not truncate replay state or lose provenance', async () => {
  const selected_cells = Array.from({ length: 150 }, (_, i) => `cell-${i}`);
  const f = fixture({
    get_state: () => ({
      selection: { cells: selected_cells.slice(0, 10), truncated: true },
    }),
    get_replay_state: () => ({ selected_cells }),
    identity: () => ({
      data: {},
      source: { url: 'data/sample', name: 'sample' },
    }),
  });
  const saved = await f.api.snapshot({
    description: 'Boundary population',
    author: 'scientist',
  });
  selected_cells.pop();
  expect(saved.state.selected_cells).toHaveLength(150);
  expect(saved.observed_state.selection.cells).toHaveLength(10);
  expect(saved).toMatchObject({
    description: 'Boundary population',
    author: 'scientist',
    source: { name: 'sample' },
    renderer: { version: 'test' },
  });
});

test('restore freezes the submitted state while awaiting validation', async () => {
  const f = fixture();
  const saved = await f.api.snapshot();
  const pending = f.api.restore_snapshot(saved);
  saved.state.view.target[0] = 99;
  await pending;
  expect(f.apply.mock.calls[0][0].view.target[0]).toBe(1);
});

test('a timed-out setter returns one error acknowledgement even if it completes later', async () => {
  jest.useFakeTimers();
  try {
    let finish;
    const operation = () =>
      new Promise((resolve) => {
        finish = resolve;
      });
    const model = { send: jest.fn() };
    const pending = handle_snapshot_message(
      model,
      {
        restore_snapshot: () => wait_for_operation(operation, 20),
      },
      { event: 'restore_snapshot', id: 12 }
    );
    await Promise.resolve();
    expect(model.send).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(20);
    await pending;
    expect(model.send).toHaveBeenCalledWith({
      event: 'apply_error',
      id: 12,
      error: 'Visualization operation timed out',
    });
    finish(['changed']);
    await Promise.resolve();
    expect(model.send).toHaveBeenCalledTimes(1);
  } finally {
    jest.useRealTimers();
  }
});

test('same names and dimensions with changed values are rejected before applying', async () => {
  const saved = await fixture().api.snapshot();
  const next = fixture();
  next.data.values[1] = 3;
  await expect(next.api.restore_snapshot(saved)).rejects.toThrow('fingerprint');
  expect(next.apply).not.toHaveBeenCalled();
});

test('schema, widget kind and canvas compatibility fail before mutation', async () => {
  const f = fixture();
  const saved = await f.api.snapshot();
  await expect(
    f.api.restore_snapshot({ ...saved, version: 2 })
  ).rejects.toThrow('schema/version');
  await expect(
    f.api.restore_snapshot({ ...saved, kind: 'landscape' })
  ).rejects.toThrow('not clustergram');
  f.dimensions.width = 800;
  await expect(f.api.restore_snapshot(saved)).rejects.toThrow('canvas size');
  expect(f.apply).not.toHaveBeenCalled();
  await f.api.restore_snapshot(saved, { allow_resize: true });
  expect(f.apply).toHaveBeenCalledTimes(1);
});

test('unverified assets require opt-in and opt-in never bypasses a mismatch', async () => {
  const f = fixture();
  f.unverified.push('remote-images');
  const saved = await f.api.snapshot();
  await expect(f.api.restore_snapshot(saved)).rejects.toThrow(
    'not fully identified'
  );
  await f.api.restore_snapshot(saved, { allow_unverified: true });
  f.apply.mockClear();
  f.data.values[0] = 55;
  await expect(
    f.api.restore_snapshot(saved, { allow_unverified: true })
  ).rejects.toThrow('fingerprint');
  expect(f.apply).not.toHaveBeenCalled();
});

test('notebook protocol returns one coordinated result and propagates restore rejection', async () => {
  const f = fixture();
  const model = { send: jest.fn() };
  await handle_snapshot_message(model, f.api, {
    event: 'capture_snapshot',
    id: 7,
  });
  const reply = model.send.mock.calls[0][0];
  expect(reply).toMatchObject({
    event: 'snapshot',
    id: 7,
    snapshot: { image: { png: 'frame-1' } },
  });
  f.data.values[0]++;
  await handle_snapshot_message(model, f.api, {
    event: 'restore_snapshot',
    id: 8,
    snapshot: reply.snapshot,
  });
  expect(model.send.mock.calls[1][0]).toMatchObject({
    event: 'apply_error',
    id: 8,
  });
  expect(f.apply).not.toHaveBeenCalled();
});
