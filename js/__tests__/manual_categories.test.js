/* global require */

// Programmatic manual categories (Clustergram.set_categories) run through the real
// ManualCategoryStore, as the category editor does. Loaded from source (no Babel).
const load = (file, exports) => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export (const|class) /gm, '$1 ');
  return new Function(`${source}\nreturn { ${exports} };`)();
};

const { ManualCategoryStore } = load(
  '../obs_store/manual_category_store.js',
  'ManualCategoryStore'
);
const { apply_manual_categories } = load(
  '../matrix/manual_categories.js',
  'apply_manual_categories'
);

const make_viz_state = ({ configured = 'cell_type' } = {}) => {
  const store = new ManualCategoryStore('col', () => ['4', '5', '6']);
  if (configured) store.setAttribute(configured);
  return {
    obs_store: { manual_cat: { col: store } },
    manual_cat: {
      config: { col: configured ? { attribute: configured } : null },
      flags: { col: Boolean(configured) },
    },
    attr: { category_colors: { 'Plasma cells': '#00aa00' } },
  };
};

describe('apply_manual_categories', () => {
  test('labels columns through the store, notifying its subscribers', () => {
    const viz_state = make_viz_state();
    const store = viz_state.obs_store.manual_cat.col;
    const emits = jest.fn();
    store.subscribe(emits, { immediate: false });
    let next = 0;
    const allocate = jest.fn(() => ['#111111', '#222222'][next++]);

    const applied = apply_manual_categories(
      viz_state,
      {
        axis: 'col',
        values: { 4: 'Goblet cells', 5: 'Plasma cells', 6: 'Goblet cells' },
      },
      allocate
    );

    expect(applied).toBe(3);
    expect(store.getValueFor('4')).toBe('Goblet cells');
    expect(store.getValueFor('6')).toBe('Goblet cells');
    expect(store.getValueFor('5')).toBe('Plasma cells');
    // A new category gets the allocator's color; a known one keeps its color.
    expect(store.colors.get('Goblet cells')).toBe('#111111');
    expect(store.colors.get('Plasma cells')).toBe('#00aa00');
    expect(allocate).toHaveBeenCalledTimes(1);
    // One emit (one repaint + one sync to Python) per category value.
    expect(emits).toHaveBeenCalledTimes(2);
  });

  test('replace clears other assignments; an empty value removes one', () => {
    const viz_state = make_viz_state();
    const store = viz_state.obs_store.manual_cat.col;
    store.updateSelection({ selection: ['6'], value: 'Old', color: '#333333' });

    apply_manual_categories(
      viz_state,
      { values: { 4: 'Goblet cells' }, replace: true },
      () => '#444444'
    );
    expect(store.getValueFor('6')).toBeNull();
    expect(store.getValueFor('4')).toBe('Goblet cells');

    apply_manual_categories(viz_state, { values: { 4: '' } }, () => '#555555');
    expect(store.getValueFor('4')).toBeNull();
  });

  test('turns manual categories on for an axis created without them', () => {
    const viz_state = make_viz_state({ configured: null });
    apply_manual_categories(
      viz_state,
      { attribute: 'clerk_cell_type', values: { 4: 'Goblet cells' } },
      () => '#666666'
    );
    expect(viz_state.manual_cat.flags.col).toBe(true);
    expect(viz_state.manual_cat.config.col.attribute).toBe('clerk_cell_type');
    expect(viz_state.obs_store.manual_cat.col.attribute).toBe(
      'clerk_cell_type'
    );

    expect(() =>
      apply_manual_categories(
        make_viz_state({ configured: null }),
        { values: { 4: 'x' } },
        () => '#777777'
      )
    ).toThrow('no manual col category');
  });
  test('marker rows reuse the color their category has on the columns', () => {
    const viz_state = make_viz_state();
    const rows = new ManualCategoryStore('row', () => ['MUC2', 'TFF3']);
    viz_state.obs_store.manual_cat.row = rows;
    const allocate = jest.fn(() => '#123456');
    apply_manual_categories(
      viz_state,
      { axis: 'col', values: { 4: 'Goblet cells' } },
      allocate
    );
    apply_manual_categories(
      viz_state,
      {
        axis: 'row',
        attribute: 'clerk_marker',
        values: { MUC2: 'Goblet cells', TFF3: 'Goblet cells' },
      },
      allocate
    );
    expect(allocate).toHaveBeenCalledTimes(1);
    expect(rows.getValueFor('MUC2')).toBe('Goblet cells');
    expect(rows.colors.get('Goblet cells')).toBe('#123456');
  });
});
