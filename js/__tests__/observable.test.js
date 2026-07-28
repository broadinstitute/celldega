/* global require */

describe('Observable', () => {
  let Observable;
  let deepEquals;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(path.join(__dirname, '../obs_store/observable.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { Observable, deepEquals };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ Observable, deepEquals } = module.exports);
  });

  test('get / getDefault reflect initial value', () => {
    const obs = Observable(5);
    expect(obs.get()).toBe(5);
    obs.set(10);
    expect(obs.get()).toBe(10);
    expect(obs.getDefault()).toBe(5);
  });

  test('subscribe fires immediately by default and on change', () => {
    const obs = Observable('a');
    const calls = [];
    obs.subscribe((v) => calls.push(v));
    obs.set('b');
    expect(calls).toEqual(['a', 'b']);
  });

  test('subscribe with immediate: false skips the initial call', () => {
    const obs = Observable('a');
    const calls = [];
    obs.subscribe((v) => calls.push(v), { immediate: false });
    obs.set('b');
    expect(calls).toEqual(['b']);
  });

  test('unsubscribe stops further notifications', () => {
    const obs = Observable(0);
    const calls = [];
    const unsubscribe = obs.subscribe((v) => calls.push(v), {
      immediate: false,
    });
    obs.set(1);
    unsubscribe();
    obs.set(2);
    expect(calls).toEqual([1]);
  });

  test('default equality does not fire when the value is unchanged', () => {
    const obs = Observable(1);
    const calls = [];
    obs.subscribe(() => calls.push(true), { immediate: false });
    obs.set(1);
    expect(calls).toHaveLength(0);
  });

  test('default (reference) equality fires for equal-content arrays', () => {
    const obs = Observable([]);
    const calls = [];
    obs.subscribe(() => calls.push(true), { immediate: false });
    obs.set([]); // new reference, same content
    expect(calls).toHaveLength(1);
  });

  test('deepEquals equality suppresses equal-content updates', () => {
    const obs = Observable([1, 2], { equals: deepEquals });
    const calls = [];
    obs.subscribe(() => calls.push(true), { immediate: false });
    obs.set([1, 2]); // same content -> no fire
    expect(calls).toHaveLength(0);
    obs.set([1, 3]); // different content -> fire
    expect(calls).toHaveLength(1);
  });

  test('update derives the next value from the current one', () => {
    const obs = Observable([1]);
    const calls = [];
    obs.subscribe((v) => calls.push(v), { immediate: false });
    obs.update((arr) => [...arr, 2]);
    expect(obs.get()).toEqual([1, 2]);
    expect(calls).toEqual([[1, 2]]);
  });

  test('deepEquals handles primitives and null', () => {
    expect(deepEquals(1, 1)).toBe(true);
    expect(deepEquals(null, null)).toBe(true);
    expect(deepEquals(null, {})).toBe(false);
    expect(deepEquals({ a: 1 }, { a: 1 })).toBe(true);
    expect(deepEquals({ a: 1 }, { a: 2 })).toBe(false);
  });
});
