/* global require */

// Snapshot cards open their view in a linked viewer without a kernel.
const fs = require('fs');
const path = require('path');

const { listen_for_view_requests } = new Function(
  `${fs
    .readFileSync(path.join(__dirname, '../viz/view_requests.js'), 'utf8')
    .replace(
      /^export const /gm,
      'const '
    )}\nreturn { listen_for_view_requests };`
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
  model.set('view_request', { id: 'a', snapshot });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(restore).toHaveBeenCalledWith(snapshot);
  expect(model.get('view_result')).toEqual({ id: 'a' });
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
    error: 'Saved view is for other data',
  });
});
