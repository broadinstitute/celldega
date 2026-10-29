/* global require */

// Drives the real category-bar code (d3 + jsdom) through the manual
// annotation flow: annotate, swap the bar's source, and swap back.
const fs = require('fs');
const path = require('path');
// d3's package exports hide dist/, so load the UMD build by path.
const d3 = require(path.join(__dirname, '../../node_modules/d3/dist/d3.js'));

const load = () => {
  const strip = (file) =>
    fs
      .readFileSync(path.join(__dirname, file), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ')
      .replace(/^export class /gm, 'class ')
      .replace(/^export function /gm, 'function ');
  const shims = `
    const ini_cat_outline_layer = () => null;
    const get_layer_update_triggers = () => ({});
    const get_mat_layers_list = () => [];
    const crop_fade_signature = () => '';
    const crop_filter_signature = () => '';
    const has_crop_filter = () => false;
    const is_axis_index_visible = () => true;
  `;
  return new Function(
    'd3',
    `${shims}${strip('../obs_store/manual_category_store.js')}${strip(
      '../ui/matrix_cat_bars.js'
    )}; return { init_matrix_cat_bars, ManualCategoryStore };`
  )(d3);
};

const make_store = () => {
  let value = null;
  const subs = new Set();
  return {
    get: () => value,
    set: (next) => {
      value = next;
      subs.forEach((fn) => fn(next));
    },
    subscribe: (fn) => subs.add(fn),
  };
};

const bar_names = (container) =>
  Array.from(
    container.querySelectorAll('.cat-bar-graph-col .cat-bar-item')
  ).map((g) => g.getAttribute('data-name'));

describe('category bars with manual annotation', () => {
  test('new manual categories appear, and survive swapping sources', async () => {
    const { init_matrix_cat_bars, ManualCategoryStore } = load();
    const col_store = new ManualCategoryStore('col', () => ['c0', 'c1', 'c2']);
    const viz_state = {
      attr: {
        cats: { row: [], col: ['leiden'] },
        names: { row: [], col: ['leiden'] },
        all_defs: { row: [], col: [] },
      },
      col_nodes: [
        { name: 'c0', 'cat-0': '0' },
        { name: 'c1', 'cat-0': '0' },
        { name: 'c2', 'cat-0': '1' },
      ],
      row_nodes: [],
      manual_cat: {
        flags: { col: true },
        config: { col: { attribute: 'cell_type' } },
      },
      obs_store: {
        manual_cat: { col: col_store },
        dendro_selection: make_store(),
        hovered_category: make_store(),
        selected_category: make_store(),
      },
      buttons: { text_active: 'blue' },
    };
    const slot = document.createElement('div');
    document.body.appendChild(slot);

    init_matrix_cat_bars(viz_state, slot);
    expect(bar_names(slot)).toEqual(['0', '1']);

    // Bootstrap sets the attribute; then the user annotates two columns.
    col_store.setAttribute('cell_type');
    col_store.updateSelection({
      selection: ['c0', 'c2'],
      value: 'Tumor',
      color: '#ff0000',
    });
    await Promise.resolve(); // bars redraw in a microtask
    expect(bar_names(slot)).toContain('Tumor');
    const tumor_rect = slot.querySelector('[data-name="Tumor"] rect');
    expect(tumor_rect.getAttribute('fill')).toBe('rgb(255, 0, 0)');

    const select = slot.querySelector('.cat-bar-source-col');
    select.value = 'leiden';
    select.dispatchEvent(new Event('change'));
    select.value = select.options[select.options.length - 1].value; // manual
    select.dispatchEvent(new Event('change'));
    expect(bar_names(slot)).toContain('Tumor');

    // A second, new category also shows up.
    col_store.updateSelection({
      selection: ['c1'],
      value: 'Stroma',
      color: '#00ff00',
    });
    await Promise.resolve();
    expect(bar_names(slot)).toEqual(
      expect.arrayContaining(['Tumor', 'Stroma'])
    );
  });
});
