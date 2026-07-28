/* global require */

describe('bind_selection', () => {
  let bind_observable_field;
  let bind_selection_to_store;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../obs_store/bind_selection.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { bind_observable_field, bind_selection_to_store };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ bind_observable_field, bind_selection_to_store } = module.exports);
  });

  // Minimal observable stand-in with the get/set surface bind relies on.
  const makeObservable = (initial) => {
    let value = initial;
    return {
      get: () => value,
      set: (next) => {
        value = next;
      },
    };
  };

  test('reads delegate to the observable', () => {
    const obs = makeObservable(['a']);
    const target = {};
    bind_observable_field(target, 'selected', obs);

    expect(target.selected).toEqual(['a']);
    obs.set(['b']);
    expect(target.selected).toEqual(['b']);
  });

  test('writes delegate to the observable', () => {
    const obs = makeObservable([]);
    const target = {};
    bind_observable_field(target, 'selected', obs);

    target.selected = ['x', 'y'];
    expect(obs.get()).toEqual(['x', 'y']);
  });

  test('seeds the observable from a pre-existing field value', () => {
    const obs = makeObservable([]);
    const target = { selected: ['seed'] };
    bind_observable_field(target, 'selected', obs);

    expect(obs.get()).toEqual(['seed']);
    expect(target.selected).toEqual(['seed']);
  });

  test('there is a single source of truth after binding', () => {
    const obs = makeObservable([]);
    const target = {};
    bind_observable_field(target, 'selected', obs);

    // Writing through either the field or the observable is observed by both.
    target.selected = [1];
    expect(obs.get()).toEqual([1]);
    obs.set([2]);
    expect(target.selected).toEqual([2]);
  });

  test('bind_selection_to_store binds both selection fields', () => {
    const viz_state = {
      obs_store: {
        selected_cats: makeObservable([]),
        selected_genes: makeObservable([]),
      },
      cats: { selected_cats: ['c1'] },
      genes: { selected_genes: ['g1'] },
    };

    bind_selection_to_store(viz_state);

    expect(viz_state.obs_store.selected_cats.get()).toEqual(['c1']);
    expect(viz_state.obs_store.selected_genes.get()).toEqual(['g1']);

    viz_state.cats.selected_cats = ['c2'];
    expect(viz_state.obs_store.selected_cats.get()).toEqual(['c2']);
  });

  test('is a no-op when target or observable is missing', () => {
    expect(() =>
      bind_observable_field(null, 'x', makeObservable(1))
    ).not.toThrow();
    expect(() => bind_observable_field({}, 'x', null)).not.toThrow();
    expect(() => bind_selection_to_store({})).not.toThrow();
  });
});
