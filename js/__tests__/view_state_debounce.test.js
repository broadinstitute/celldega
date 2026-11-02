/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import .*;$/gm, '')
    .replace(/^export const /gm, 'const ');

test('viewport debounce is independent for each Landscape', () => {
  jest.useFakeTimers();
  const calc = jest.fn();
  const onChange = new Function(
    'calc_viewport',
    `${read('utils/debounce.js')}\n${read('deck-gl/core/on_view_state_change.js')}\nreturn on_view_state_change;`
  )(calc);
  const first = { custom_callbacks: {} };
  const second = { custom_callbacks: {} };
  onChange({ viewState: { zoom: 1 } }, {}, {}, first);
  onChange({ viewState: { zoom: 2 } }, {}, {}, second);
  onChange({ viewState: { zoom: 3 } }, {}, {}, first);
  jest.advanceTimersByTime(200);
  expect(calc).toHaveBeenCalledTimes(2);
  expect(
    calc.mock.calls.map(([view, , , state]) => [view.zoom, state])
  ).toEqual([
    [2, second],
    [3, first],
  ]);
  jest.useRealTimers();
});
