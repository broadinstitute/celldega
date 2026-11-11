/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../viz/snapshot.js'), 'utf8')
  .replace(/^import .*;$/gm, '')
  .replace(/^export const /gm, 'const ');
const {
  create_snapshot_api,
  handle_snapshot_message,
  wait_for_operation,
  hash_names,
  names_signature,
  identity_differences,
  landscape_identity,
  consume_initial_snapshot,
} = new Function(
  `const CELLDEGA_VERSION = "test"; ${source}; return { create_snapshot_api, handle_snapshot_message, wait_for_operation, hash_names, names_signature, identity_differences, landscape_identity, consume_initial_snapshot };`
)();

test('initial notebook replay is cleared before awaiting and acknowledged exactly once', async () => {
  const request = {
    event: 'restore_snapshot',
    id: 4,
    snapshot: { state: {} },
    options: { allow_resize: true },
  };
  let value = request;
  let finish;
  const model = {
    get: () => value,
    set: (_key, next) => {
      value = next;
    },
    save_changes: jest.fn(),
    send: jest.fn(),
  };
  const api = {
    restore_snapshot: jest.fn(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    ),
  };
  const pending = consume_initial_snapshot(model, api);
  expect(value).toEqual({});
  await consume_initial_snapshot(model, api);
  expect(api.restore_snapshot).toHaveBeenCalledTimes(1);
  expect(api.restore_snapshot).toHaveBeenCalledWith(request.snapshot, {
    allow_resize: true,
  });
  finish(['moved']);
  await pending;
  expect(model.send).toHaveBeenCalledWith({
    event: 'applied',
    id: 4,
    done: ['moved'],
  });
});

test('initial replay failure is acknowledged and visible, without retry on rerender', async () => {
  let value = { event: 'restore_snapshot', id: 7, snapshot: {} };
  const model = {
    get: () => value,
    set: (_key, next) => {
      value = next;
    },
    send: jest.fn(),
  };
  const api = {
    restore_snapshot: jest.fn(async () => {
      throw new Error('data revision differs');
    }),
  };
  const el = document.createElement('div');
  await consume_initial_snapshot(model, api, el);
  await consume_initial_snapshot(model, api, el);
  expect(model.send).toHaveBeenCalledTimes(1);
  expect(model.send).toHaveBeenCalledWith({
    event: 'apply_error',
    id: 7,
    error: 'data revision differs',
  });
  expect(el.querySelector('[role="alert"]').textContent).toContain(
    'data revision differs'
  );
});

const fixture = (overrides = {}) => {
  const data = { rows: ['g1', 'g2'], cols: ['a', 'b'], revision: '' };
  let position = 1;
  const dimensions = { width: 500, height: 400 };
  const apply = jest.fn(async (state) => {
    position = state.view.target[0];
    return ['moved'];
  });
  const view = () => ({ target: [position, 0], zoom: [0, 0] });
  const api = create_snapshot_api({
    kind: 'clustergram',
    get_state: () => ({ kind: 'clustergram', view: view() }),
    get_replay_state: () => ({ view: view() }),
    capture_raster: () => ({
      png: `frame-${position}`,
      width: 500,
      height: 400,
    }),
    apply_state: apply,
    identity: () => ({
      revision: data.revision,
      rows: names_signature(data.rows),
      cols: names_signature(data.cols),
    }),
    viewport: () => dimensions,
    ...overrides,
  });
  return {
    api,
    data,
    dimensions,
    apply,
    move: (x) => {
      position = x;
    },
  };
};

test('image, observations and replay settings are read when captured', async () => {
  const f = fixture();
  const pending = f.api.snapshot();
  f.move(9);
  const snapshot = await pending;
  expect(snapshot.version).toBe(2);
  expect(snapshot.image.png).toBe('frame-1');
  expect(snapshot.observed_state.view.target).toEqual([1, 0]);
  expect(snapshot.state.view.target).toEqual([1, 0]);
  const fresh = fixture();
  await fresh.api.restore_snapshot(JSON.parse(JSON.stringify(snapshot)));
  expect(fresh.apply).toHaveBeenCalledWith(snapshot.state);
});

test('bounded observations do not truncate replay state or lose provenance', async () => {
  const selected_cells = Array.from({ length: 150 }, (_, i) => `cell-${i}`);
  const f = fixture({
    get_state: () => ({
      selection: { cells: selected_cells.slice(0, 10), truncated: true },
    }),
    get_replay_state: () => ({ selected_cells }),
    source: () => ({ url: 'data/sample', name: 'sample' }),
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

test('different data is rejected before applying, naming what differs', async () => {
  const saved = await fixture().api.snapshot();
  const next = fixture();
  next.data.cols = ['a', 'c'];
  await expect(next.api.restore_snapshot(saved)).rejects.toThrow(
    'does not match the loaded data: columns differ'
  );
  expect(next.apply).not.toHaveBeenCalled();
});

test('a declared revision is compared only when both sides have one', async () => {
  const f = fixture();
  f.data.revision = 'release-1';
  const saved = await f.api.snapshot();
  const unrevised = fixture();
  await unrevised.api.restore_snapshot(saved);
  expect(unrevised.apply).toHaveBeenCalledTimes(1);
  const other = fixture();
  other.data.revision = 'release-2';
  await expect(other.api.restore_snapshot(saved)).rejects.toThrow(
    'data revision differ'
  );
});

test('schema, widget kind, identity and canvas compatibility fail before mutation', async () => {
  const f = fixture();
  const saved = await f.api.snapshot();
  await expect(
    f.api.restore_snapshot({ ...saved, version: 1 })
  ).rejects.toThrow('schema/version');
  await expect(
    f.api.restore_snapshot({ ...saved, kind: 'landscape' })
  ).rejects.toThrow('not clustergram');
  await expect(
    f.api.restore_snapshot({ ...saved, identity: {} })
  ).rejects.toThrow('no data identity');
  f.dimensions.width = 800;
  await expect(f.api.restore_snapshot(saved)).rejects.toThrow('canvas size');
  expect(f.apply).not.toHaveBeenCalled();
  await f.api.restore_snapshot(saved, { allow_resize: true });
  expect(f.apply).toHaveBeenCalledTimes(1);
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
  f.data.rows = ['g1', 'g3'];
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

describe('name-based identity', () => {
  test('hashes depend on every name and on their boundaries and order', () => {
    expect(hash_names(['a', 'b'])).toMatch(/^[0-9a-f]{14}$/);
    expect(hash_names(['a', 'b'])).toBe(hash_names(['a', 'b']));
    expect(hash_names(['ab', 'c'])).not.toBe(hash_names(['a', 'bc']));
    expect(hash_names(['a', 'b'])).not.toBe(hash_names(['b', 'a']));
    expect(hash_names([1, 2])).toBe(hash_names(['1', '2']));
  });

  test('a signature is computed once per array and again if it grows', () => {
    const names = ['c1', 'c2'];
    const first = names_signature(names);
    expect(first).toEqual({ count: 2, hash: hash_names(names) });
    names.push('c3');
    expect(names_signature(names)).toEqual({
      count: 3,
      hash: hash_names(['c1', 'c2', 'c3']),
    });
    expect(names_signature(null)).toEqual({ count: 0, hash: '' });
  });

  test('only parts the saved view records are compared', () => {
    const current = {
      revision: '',
      cells: { count: 2, hash: 'x' },
      genes: { count: 1, hash: 'y' },
    };
    expect(
      identity_differences({ cells: { count: 2, hash: 'x' } }, current)
    ).toEqual([]);
    expect(
      identity_differences(
        { cells: { count: 3, hash: 'z' }, genes: { count: 1, hash: 'y' } },
        current
      )
    ).toEqual(['cells']);
  });

  test('a Landscape is identified by its cells, genes and cluster labels', () => {
    const state = {
      model: { get: (key) => (key === 'data_revision' ? 'r1' : undefined) },
      cats: {
        cell_names_array: ['c1', 'c2'],
        cell_cats: ['A', 'B'],
        inst_cell_attr: 'leiden',
      },
      genes: { gene_names: ['G1'] },
    };
    const identity = landscape_identity(state);
    expect(identity).toEqual({
      revision: 'r1',
      cells: { count: 2, hash: hash_names(['c1', 'c2']) },
      genes: { count: 1, hash: hash_names(['G1']) },
      clusters: { attribute: 'leiden', count: 2, hash: hash_names(['A', 'B']) },
    });
    // Re-clustering replaces the labels array, so the identity follows it.
    state.cats.cell_cats = ['A', 'A'];
    expect(identity_differences(identity, landscape_identity(state))).toEqual([
      'cluster labels',
    ]);
  });
});
