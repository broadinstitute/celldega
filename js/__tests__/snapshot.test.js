/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../viz/snapshot.js'), 'utf8')
  .replace(/^import .*;$/gm, 'const CELLDEGA_VERSION = "test";')
  .replace(/^export const /gm, 'const ');
const { create_snapshot_api, handle_snapshot_message } = new Function(
  'globalThis',
  'TextEncoder',
  `${source}; return { create_snapshot_api, handle_snapshot_message };`
)({ crypto: require('crypto').webcrypto }, require('util').TextEncoder);

const fixture = () => {
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
