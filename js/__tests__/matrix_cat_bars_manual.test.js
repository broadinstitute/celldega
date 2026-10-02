/* global require */

// Manual-category breakdowns read the ManualCategoryStore API (`attribute`,
// `getValueFor`). They previously called methods the store does not have,
// which threw while rendering any Clustergram that combined static and
// manual categories.
const fs = require('fs');
const path = require('path');

describe('compute_manual_category_breakdown', () => {
  let compute_manual_category_breakdown;
  let get_bar_sources;
  let compute_breakdown;
  let MANUAL_SOURCE;
  let ManualCategoryStore;

  beforeAll(() => {
    const strip = (file) =>
      fs
        .readFileSync(path.join(__dirname, file), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ')
        .replace(/^export class /gm, 'class ')
        .replace(/^export function /gm, 'function ');

    const shims = `
      const d3 = {};
      const is_axis_index_visible = () => true;
    `;
    ({ ManualCategoryStore } = new Function(
      `${strip('../obs_store/manual_category_store.js')}; return { ManualCategoryStore };`
    )());
    ({
      compute_manual_category_breakdown,
      get_bar_sources,
      compute_breakdown,
      MANUAL_SOURCE,
    } = new Function(
      `${shims}${strip('../ui/matrix_cat_bars.js')}; return { compute_manual_category_breakdown, get_bar_sources, compute_breakdown, MANUAL_SOURCE };`
    )());
  });

  test('counts manual assignments per value using the store API', () => {
    const store = new ManualCategoryStore('col', () => ['c0', 'c1', 'c2']);
    store.setAttribute('cell_type');
    store.updateSelection({ selection: ['c0', 'c2'], value: 'T cell' });

    const viz_state = {
      obs_store: { manual_cat: { col: store } },
      col_nodes: [{ name: 'c0' }, { name: 'c1' }, { name: 'c2' }],
    };

    const result = compute_manual_category_breakdown(viz_state, 'col');
    expect(result.attr_name).toBe('cell_type');
    expect(result.data).toEqual([{ name: 'T cell', value: 2 }]);
  });

  test('lists static attributes plus the manual category as bar sources', () => {
    const store = new ManualCategoryStore('col', () => ['c0', 'c1']);
    const viz_state = {
      attr: { cats: { col: ['leiden'] }, names: { col: ['leiden'] } },
      obs_store: { manual_cat: { col: store } },
      manual_cat: { flags: { col: false }, config: {} },
    };

    // No manual category yet: only the static attribute.
    expect(get_bar_sources(viz_state, 'col')).toEqual([
      { value: 'leiden', label: 'leiden' },
    ]);

    store.setAttribute('cell_type');
    expect(get_bar_sources(viz_state, 'col')).toEqual([
      { value: 'leiden', label: 'leiden' },
      { value: MANUAL_SOURCE, label: 'cell_type' },
    ]);

    // Annotating registers the manual attribute among the categories too; it
    // must still be listed only once.
    viz_state.attr.cats.col.push('cell_type');
    expect(get_bar_sources(viz_state, 'col')).toEqual([
      { value: 'leiden', label: 'leiden' },
      { value: MANUAL_SOURCE, label: 'cell_type' },
    ]);
  });

  test('breaks down the chosen source, optionally within a selection', () => {
    const store = new ManualCategoryStore('col', () => ['c0', 'c1', 'c2']);
    store.setAttribute('cell_type');
    store.updateSelection({ selection: ['c1', 'c2'], value: 'B cell' });
    const viz_state = {
      attr: { cats: { col: ['leiden'] }, names: { col: ['leiden'] } },
      obs_store: { manual_cat: { col: store } },
      col_nodes: [
        { name: 'c0', 'cat-0': '0' },
        { name: 'c1', 'cat-0': '0' },
        { name: 'c2', 'cat-0': '1' },
      ],
    };

    expect(compute_breakdown(viz_state, 'col', 'leiden').data).toEqual([
      { name: '0', value: 2 },
      { name: '1', value: 1 },
    ]);
    expect(
      compute_breakdown(viz_state, 'col', 'leiden', ['c1', 'c2']).data
    ).toEqual([
      { name: '0', value: 1 },
      { name: '1', value: 1 },
    ]);
    expect(compute_breakdown(viz_state, 'col', MANUAL_SOURCE).data).toEqual([
      { name: 'B cell', value: 2 },
    ]);
  });
});
