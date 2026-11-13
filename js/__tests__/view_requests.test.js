/* global require */

// Snapshot cards open their view in a linked viewer without a kernel.
const fs = require('fs');
const path = require('path');

const { listen_for_view_requests, announce_view } = new Function(
  `${fs
    .readFileSync(path.join(__dirname, '../viz/view_requests.js'), 'utf8')
    .replace(
      /^export const /gm,
      'const '
    )}\nreturn { listen_for_view_requests, announce_view };`
)();

const make_model = () => {
  const values = {};
  const listeners = {};
  return {
    get: (key) => values[key],
    set: (key, value) => {
      values[key] = value;
      (listeners[`change:${key}`] || []).forEach((fn) => fn());
    },
    save_changes: jest.fn(),
    on: (event, fn) => {
      (listeners[event] ||= []).push(fn);
    },
    off: (event, fn) => {
      listeners[event] = (listeners[event] || []).filter((f) => f !== fn);
    },
  };
};

test('a request opens the view once and answers with its id', async () => {
  const model = make_model();
  const restore = jest.fn(async () => ['moved the view']);
  const stop = listen_for_view_requests(model, restore);
  const snapshot = { kind: 'landscape', state: {} };
  model.set('view_request', { id: 'a', name: 'Glomerulus', snapshot });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(restore).toHaveBeenCalledWith(snapshot);
  // Every linked card hears which Snapshot is shown.
  expect(model.get('view_result')).toEqual({ id: 'a', shown: 'Glomerulus' });
  // The same request again (e.g. a synced echo) is not replayed.
  model.set('view_request', { id: 'a', snapshot });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(restore).toHaveBeenCalledTimes(1);
  stop();
  model.set('view_request', { id: 'b', snapshot });
  expect(restore).toHaveBeenCalledTimes(1);
});

test('a failed restore is reported to the card', async () => {
  const model = make_model();
  listen_for_view_requests(model, async () => {
    throw new Error('Saved view is for other data');
  });
  model.set('view_request', { id: 'c', snapshot: {} });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(model.get('view_result')).toEqual({
    id: 'c',
    shown: '',
    error: 'Saved view is for other data',
  });
});

test('requests made before the viewer rendered are not replayed', async () => {
  // A reloaded page's links copy each card's last request into the viewer.
  const model = make_model();
  const restore = jest.fn(async () => []);
  listen_for_view_requests(model, restore, { since: 1000 });
  model.set('view_request', { id: 'old', at: 500, snapshot: {} });
  model.set('view_request', { id: 'new', at: 1500, snapshot: {} });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(restore).toHaveBeenCalledTimes(1);
  expect(model.get('view_result').id).toBe('new');
});

test('announce_view tells the cards what is shown, or that nothing is', () => {
  const model = make_model();
  announce_view(model, 'Medulla');
  expect(model.get('view_result')).toEqual({ id: null, shown: 'Medulla' });
  announce_view(model, '');
  expect(model.get('view_result')).toEqual({ id: null, shown: '' });
  const saves = model.save_changes.mock.calls.length;
  announce_view(model, ''); // already cleared: nothing to send
  expect(model.save_changes.mock.calls.length).toBe(saves);
});
