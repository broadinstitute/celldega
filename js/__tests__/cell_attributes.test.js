/* global require */

// Showing a Landscape's cells by another attribute: per-cell cell_attr columns
// (their own categories) or label sets naming clusters (display only, selections
// stay clusters), with the bar graph and the ▾ menu beside CELL.

const fs = require('fs');
const path = require('path');

const strip = (file) =>
  fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

// Just what cell_attributes.js uses of d3 and hexToRgb.
const SHIMS = `
  const d3 = {
    rgb: (color) => {
      const [r, g, b] = String(color).match(/\\d+/g).map(Number);
      return { r, g, b };
    },
    interpolateRainbow: (t) => \`rgb(\${Math.round(t * 200)}, 10, 20)\`,
  };
  const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.substr(i, 2), 16));
  const CONTROL_FONT_SIZE = '9px';
`;

const api = new Function(
  `${SHIMS}
   ${strip('../global_variables/cell_attributes.js')}
   ${strip('../ui/cell_attribute_menu.js')}
   return { set_cell_attribute, cell_attribute_options, group_bar_data,
     clusters_of_bar, selected_bar_names, bar_name_of, reset_cell_attribute,
     make_cell_attribute_menu };`
)();

const RED = [255, 0, 0];
const GREEN = [0, 255, 0];
const BLUE = [0, 0, 255];

const make_viz_state = ({ label_sets = {}, meta_cell = false } = {}) => {
  const model_state = {
    label_sets,
    cell_attr_colors: { cell_type: { B: '#0000ff' } },
  };
  const cats = {
    inst_cell_attr: 'leiden',
    cell_names_array: ['a', 'b', 'c', 'd'],
    cell_cats: ['4', '4', '7', '9'],
    color_dict_cluster: { 4: RED, 7: GREEN, 9: BLUE },
    cluster_counts: [
      { name: '4', value: 2 },
      { name: '7', value: 1 },
      { name: '9', value: 1 },
    ],
    has_meta_cell: meta_cell,
    meta_cell_attr: meta_cell ? ['leiden', 'cell_type', 'color'] : [],
    meta_cell: meta_cell
      ? {
          a: ['4', 'B', '#f00'],
          b: ['4', 'T', '#f00'],
          c: ['7', 'B', '#0f0'],
          d: ['9', 'nan', '#00f'],
        }
      : {},
  };
  return {
    cats,
    model: {
      get: (key) => model_state[key],
      set: (key, value) => {
        model_state[key] = value;
      },
    },
  };
};

const CELL_TYPES = {
  cell_type: {
    labels: { 4: 'Goblet', 7: 'Goblet', 9: '' },
    colors: { Goblet: '#00ff00' },
  },
  clerk_cell_type: { labels: { 4: 'Enterocyte' } },
};

describe('label sets: clusters shown by their labels', () => {
  test('the menu offers the clusters, per-cell attributes and label sets', () => {
    const viz_state = make_viz_state({
      label_sets: CELL_TYPES,
      meta_cell: true,
    });
    expect(
      api.cell_attribute_options(viz_state).map((o) => [o.value, o.kind])
    ).toEqual([
      ['', null],
      ['cell_type', 'cell'], // a per-cell column wins over a set of that name
      ['clerk_cell_type', 'labels'],
    ]);
    // Without cell metadata the clusters are just "cluster".
    expect(api.cell_attribute_options(make_viz_state())[0].label).toBe(
      'cluster'
    );
  });

  test('labeled clusters take their label color; bars group by label', () => {
    const viz_state = make_viz_state({ label_sets: CELL_TYPES });
    const colors = viz_state.cats.color_dict_cluster;
    const result = api.set_cell_attribute(viz_state, 'cell_type');
    expect(result).toEqual({ changed_categories: false });
    // In place: the bar graph and layers hold this object.
    expect(viz_state.cats.color_dict_cluster).toBe(colors);
    expect(colors[4]).toEqual([0, 255, 0]);
    expect(colors[7]).toEqual([0, 255, 0]);
    expect(colors[9]).toEqual(BLUE); // unlabeled ('') keeps its own color
    expect(colors.Goblet).toEqual([0, 255, 0]);
    // The cells keep their clusters.
    expect(viz_state.cats.cell_cats).toEqual(['4', '4', '7', '9']);
    expect(
      api.group_bar_data(viz_state, viz_state.cats.cluster_counts)
    ).toEqual([
      { name: 'Goblet', value: 3 },
      { name: '9', value: 1 },
    ]);
    expect(api.clusters_of_bar(viz_state, 'Goblet')).toEqual(['4', '7']);
    expect(api.selected_bar_names(viz_state, ['7', '9'])).toEqual([
      'Goblet',
      '9',
    ]);
  });

  test("a label without a color takes its first cluster's", () => {
    const viz_state = make_viz_state({ label_sets: CELL_TYPES });
    api.set_cell_attribute(viz_state, 'clerk_cell_type');
    expect(viz_state.cats.color_dict_cluster.Enterocyte).toEqual(RED);
    // Switching sets and back to the clusters restores their colors exactly.
    api.set_cell_attribute(viz_state, 'cell_type');
    api.set_cell_attribute(viz_state, '');
    expect(viz_state.cats.color_dict_cluster).toEqual({
      4: RED,
      7: GREEN,
      9: BLUE,
    });
    expect(api.group_bar_data(viz_state, [{ name: '4', value: 2 }])).toEqual([
      { name: '4', value: 2 },
    ]);
  });

  test('unknown attributes are refused', () => {
    expect(() => api.set_cell_attribute(make_viz_state(), 'nope')).toThrow(
      'unknown cell attribute: nope'
    );
  });
});

describe('per-cell attributes (cell_attr columns)', () => {
  test('replace the categories, counts and colors; the clusters come back', () => {
    const viz_state = make_viz_state({ meta_cell: true });
    const { cats } = viz_state;
    expect(api.set_cell_attribute(viz_state, 'cell_type')).toEqual({
      changed_categories: true,
    });
    expect(cats.cell_cats).toEqual(['B', 'T', 'B', 'N.A.']);
    expect(cats.inst_cell_attr).toBe('cell_type');
    expect(cats.cluster_counts[0]).toEqual({ name: 'B', value: 2 });
    expect(cats.color_dict_cluster.B).toEqual(BLUE); // from cell_attr_colors
    expect(cats.color_dict_cluster.T).toHaveLength(3); // a palette color
    expect(cats.color_dict_cluster[4]).toBeUndefined();
    // The clusters' name returns to them.
    expect(api.set_cell_attribute(viz_state, 'leiden')).toEqual({
      changed_categories: true,
    });
    expect(cats.cell_cats).toEqual(['4', '4', '7', '9']);
    expect(cats.inst_cell_attr).toBe('leiden');
    expect(cats.color_dict_cluster[4]).toEqual(RED);
  });

  test('reset (new data) forgets the kept clusters', () => {
    const viz_state = make_viz_state({ meta_cell: true });
    api.set_cell_attribute(viz_state, 'cell_type');
    api.reset_cell_attribute(viz_state.cats);
    expect(viz_state.cats.base).toBeNull();
    expect(viz_state.cats.attribute).toBe('');
    expect(viz_state.cats.inst_cell_attr).toBe('leiden');
  });
});

describe('the ▾ menu beside CELL', () => {
  const make_menu = (viz_state) => {
    const row = document.createElement('div');
    const cell = document.createElement('div');
    cell.textContent = 'CELL';
    row.appendChild(cell);
    const picks = [];
    const menu = api.make_cell_attribute_menu(viz_state, cell, (name) =>
      picks.push(name)
    );
    return {
      row,
      cell,
      menu,
      picks,
      select: menu.element.querySelector('select'),
    };
  };

  test('hidden with only the clusters; lists the choices once there are more', () => {
    const viz_state = make_viz_state();
    const { cell, menu, select } = make_menu(viz_state);
    expect(cell.nextSibling).toBe(menu.element);
    expect(menu.element.style.display).toBe('none');
    viz_state.model.set('label_sets', CELL_TYPES);
    menu.update();
    expect(menu.element.style.display).toBe('inline-block');
    expect([...select.options].map((o) => o.textContent)).toEqual([
      'CLUSTER',
      'CELL_TYPE',
      'CLERK_CELL_TYPE',
    ]);
    expect(menu.element.firstChild.textContent).toBe('▾');
  });

  test('picking calls back and keeps showing the current choice', () => {
    const viz_state = make_viz_state({ label_sets: CELL_TYPES });
    const { select, picks } = make_menu(viz_state);
    select.value = 'cell_type';
    select.dispatchEvent(new Event('change'));
    expect(picks).toEqual(['cell_type']);
    expect(select.value).toBe(''); // until the switch lands
    api.set_cell_attribute(viz_state, 'cell_type');
    select.dispatchEvent(new Event('change'));
    expect(select.title).toContain('cell_type');
  });
});

describe('clicking a label bar selects its clusters', () => {
  const bar_plot = new Function(
    `${SHIMS}
     const update_cat = (cats, cat) => { cats.cat = cat; };
     const update_selected_cats = (cats, next, obs_store) => {
       cats.reset_cat =
         next.length === cats.selected_cats.length &&
         next.every((value, index) => value === cats.selected_cats[index]);
       cats.selected_cats = cats.reset_cat ? [] : next;
       obs_store.selected_cats.set(cats.selected_cats);
     };
     const noop = () => {};
     const update_selected_genes = noop;
     const new_toggle_cell_layer_visibility = noop;
     const refresh_nbhd_cloud_cluster_cells = noop;
     const refresh_nbhd_cloud_gene_cells = noop;
     const apply_nbhd_cloud_slice_filter = noop;
     const select_nbhd_cloud_gene = noop;
     const toggle_nbhd_cloud_cluster_selection = noop;
     const toggle_trx_layer_visibility = noop;
     const toggle_slider = noop;
     const refresh_layer = noop;
     const register_ui_cleanup = noop;
     const make_gene_hover_tooltip = () => ({});
     const escape_html = (value) => String(value ?? '');
     ${strip('../global_variables/cell_attributes.js')}
     ${strip('../ui/bar_plot.js')}
     return { bar_callback_cat, cluster_bar_tooltip_html, set_cell_attribute };`
  )();

  test('one click: all of them; again: none; shift-click adds the group', () => {
    const viz_state = make_viz_state({ label_sets: CELL_TYPES });
    const bars = { selectAll: () => ({ style: () => {} }) };
    Object.assign(viz_state, {
      genes: { svg_bar_gene: bars },
      sliders: {},
      nbhd: {},
      obs_store: {
        deck_check: { get: () => ({}), set: () => {} },
        selected_cats: { set: () => {} },
      },
    });
    Object.assign(viz_state.cats, {
      cat: 'cluster',
      selected_cats: [],
      svg_bar_cluster: bars,
    });
    bar_plot.set_cell_attribute(viz_state, 'cell_type');
    const click = (name, shiftKey = false) =>
      bar_plot.bar_callback_cat({ shiftKey }, { name }, null, {}, viz_state);
    click('Goblet');
    expect(viz_state.cats.selected_cats).toEqual(['4', '7']);
    click('Goblet');
    expect(viz_state.cats.selected_cats).toEqual([]);
    click('9');
    click('Goblet', true);
    expect(viz_state.cats.selected_cats).toEqual(['9', '4', '7']);
    click('Goblet', true);
    expect(viz_state.cats.selected_cats).toEqual(['9']);
    // Its tooltip names the clusters.
    expect(
      bar_plot.cluster_bar_tooltip_html(
        { name: 'Goblet', value: 3 },
        { clusters: ['4', '7'] }
      )
    ).toContain('clusters: 4, 7');
  });
});

test('the CELL slider narrows while the caret shows', () => {
  const viz_state = make_viz_state();
  const cell = document.createElement('div');
  document.createElement('div').appendChild(cell);
  const slider = document.createElement('input');
  slider.style.width = '75px';
  const menu = api.make_cell_attribute_menu(viz_state, cell, () => {}, {
    slider,
  });
  expect(slider.style.width).toBe('75px'); // only the clusters: no caret
  viz_state.model.set('label_sets', CELL_TYPES);
  menu.update();
  expect(slider.style.width).toBe('60px');
  expect(menu.element.firstChild.style.fontSize).toBe('12px');
  viz_state.model.set('label_sets', {});
  menu.update();
  expect(slider.style.width).toBe('75px');
});

describe('the cell tooltip names the attribute shown', () => {
  const { make_tooltip, set_cell_attribute } = new Function(
    `${SHIMS}
     const escape_html = (value) => String(value ?? '').replace(/</g, '&lt;');
     const gene_info_tooltip_html = () => '';
     const refresh_gene_tooltip_async = () => {};
     const has_uniprot_info = () => false;
     const get_point_cloud_source_index = (viz_state, index) => index;
     const is_cluster_color_mode = (cats) => !cats.cat || cats.cat === 'cluster';
     ${strip('../global_variables/cell_attributes.js')}
     ${strip('../deck-gl/utils/tooltips.js')}
     return { make_tooltip, set_cell_attribute };`
  )();
  const hover = (viz_state, index) => {
    viz_state.root ??= document.createElement('div');
    return make_tooltip(viz_state, { index, layer: { id: 'cell-layer-x' } })
      ?.html;
  };

  test('clusters: just the cluster', () => {
    const html = hover(make_viz_state({ label_sets: CELL_TYPES }), 0);
    expect(html).toContain('cell: a');
    expect(html).toContain('cluster: 4');
    expect(html).not.toContain('cell_type');
  });

  test('a label set: its label (or unlabeled), then the cluster', () => {
    const viz_state = make_viz_state({ label_sets: CELL_TYPES });
    set_cell_attribute(viz_state, 'cell_type');
    expect(hover(viz_state, 2)).toContain(
      '<div>cell_type: Goblet</div><div>cluster: 7</div>'
    );
    expect(hover(viz_state, 3)).toContain('cell_type: <i>unlabeled</i>');
  });

  test("a per-cell attribute: its value, then the cell's cluster", () => {
    const viz_state = make_viz_state({ meta_cell: true });
    set_cell_attribute(viz_state, 'cell_type');
    expect(hover(viz_state, 1)).toContain(
      '<div>cell_type: T</div><div>cluster: 4</div>'
    );
  });
});
