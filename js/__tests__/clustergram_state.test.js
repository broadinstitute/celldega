/* global require */

// Clustergram state snapshot (getter half of the Clustergram Viz API). Loaded from
// source like the other tests (no Babel); the crop/display helpers are shimmed with
// a simple layout: each displayed item occupies a 10-unit slot in display order.
const load_clustergram_state = (display) => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(
      path.join(__dirname, '../matrix/clustergram_state.js'),
      'utf8'
    )
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
  const replay = fs
    .readFileSync(path.join(__dirname, '../matrix/replay_controls.js'), 'utf8')
    .replace(/^export const /gm, 'const ');
  const shims = `
    const get_axis_display_state = (viz_state, axis) => ({
      visible_indices: display[axis].slice(),
    });
    const get_axis_indices_in_range = (viz_state, axis, min, max) =>
      display[axis].filter((raw, i) => {
        const center = (i + 0.5) * 10;
        return center >= min && center <= max;
      });
  `;
  const module = { exports: {} };
  new Function(
    'module',
    'display',
    `${shims}\n${replay}\n${source}\nmodule.exports = { get_clustergram_state, get_clustergram_controls, get_clustergram_replay_state, visible_world_bounds, apply_clustergram_state };`
  )(module, display);
  return module.exports;
};

// Rows display as g1, g0, g2, g3; columns as c2, c0, c1.
const DISPLAY = { row: [1, 0, 2, 3], col: [2, 0, 1] };

const make_viz_state = ({ visible_height = 40 } = {}) => ({
  row_nodes: [{ name: 'g0' }, { name: 'g1' }, { name: 'g2' }, { name: 'g3' }],
  col_nodes: [{ name: 'c0' }, { name: 'c1' }, { name: 'c2' }],
  order: { current: { row: 'clust', col: 'rank' } },
  attr: {
    names: { row: ['marker'], col: ['cell_type', 'score'] },
    all_defs: {
      row: [
        {
          name: 'marker',
          type: 'categorical',
          values: ['4', '4', '5', '5'],
          color_map: { 4: '#f00', 5: '#0f0' },
        },
      ],
      col: [
        {
          name: 'cell_type',
          type: 'categorical',
          values: ['Goblet', 'Plasma', null],
          color_map: { Goblet: '#00f', Plasma: '#0ff', Other: '#ccc' },
        },
        { name: 'score', type: 'numeric', values: [0.12345, 2, 3] },
      ],
    },
  },
  dendro: {
    sliders: { row_percent: 40 },
    group_info: {
      row: [
        { name: '2', pos_mid: 5, all_names: ['g2', 'g3'] },
        { name: '1', pos_mid: 1, all_names: ['g1', 'g0'] },
      ],
    },
  },
  rank_view: {
    views: [{ level: 1 }, { level: 3 }],
    current: 3,
    level_unit: 'per_cluster',
    view_type: 'rank_genes_groups',
    // c0's markers: g3 then g1; c2's: g2.
    markers: { c0: [3, 1], c2: [2] },
  },
  obs_store: {
    selected_genes: { get: () => ['g1'] },
    dendro_selection: { get: () => null },
  },
  labels: { highlighted_genes: new Set(['g2']) },
  click: { type: 'row_label', value: 'g1' },
  crop: { filter: { row: null, col: [0, 1, 2] } },
  mat: {
    net_mat: [
      [1, 2, 3],
      [4, 5, 6],
      [7, 8, 9],
      [10, 11, 12],
    ],
    mat_data: [
      { row: 1, col: 0, size_value: 0.5 },
      { row: 2, col: 2, size_value: 0.25 },
    ],
  },
  // A 100x100 px matrix view showing world x 0..30 and y 0..visible_height.
  deck_mat: {
    viewManager: {
      getViewports: () => [
        {
          id: 'matrix',
          width: 100,
          height: 100,
          unproject: ([x, y]) => [(x / 100) * 30, (y / 100) * visible_height],
        },
      ],
    },
  },
});

describe('get_clustergram_state', () => {
  const { get_clustergram_state, visible_world_bounds } =
    load_clustergram_state(DISPLAY);

  test('viewport mode reports only what is on screen, in display order', () => {
    // Only the top two row slots (centers 5 and 15) fit in y 0..20.
    const state = get_clustergram_state(make_viz_state({ visible_height: 20 }));
    expect(state.on_screen_known).toBe(true);
    expect(state.rows.names).toEqual(['g1', 'g0']);
    expect(state.rows).toMatchObject({
      selection_mode: 'viewport',
      total: 2,
      truncated: false,
      displayed: 4,
      count: 4,
    });
    expect(state.cols.names).toEqual(['c2', 'c0', 'c1']);
  });

  test('ranked and named selections, with caps and missing names', () => {
    const viz_state = make_viz_state();
    const ranked = get_clustergram_state(viz_state, {
      rows: 'ranked',
      max_rows: 2,
    });
    expect(ranked.rows.names).toEqual(['g1', 'g0']);
    expect(ranked.rows).toMatchObject({ total: 4, truncated: true });

    const named = get_clustergram_state(viz_state, {
      rows: ['g3', 'nope', 'g0'],
    });
    expect(named.rows.names).toEqual(['g3', 'g0']);
    expect(named.rows.missing).toEqual(['nope']);
  });

  test('attributes follow the reported items; colors only for present values', () => {
    const state = get_clustergram_state(make_viz_state());
    const [cell_type, score] = state.cols.attributes;
    expect(cell_type.values).toEqual([null, 'Goblet', 'Plasma']);
    expect(cell_type.colors).toEqual({ Goblet: '#00f', Plasma: '#0ff' });
    expect(score.values).toEqual([3, 0.123, 2]);
    expect(state.rows.attributes[0].values).toEqual(['4', '4', '5', '5']);
  });

  test('order, dendrogram groups, marker level and selection', () => {
    const state = get_clustergram_state(make_viz_state());
    expect(state.rows.order).toEqual({ name: 'clust', label: 'clustered' });
    expect(state.cols.order).toEqual({ name: 'rank', label: 'sum' });
    expect(state.rows.groups.cut_percent).toBe(40);
    expect(state.rows.groups.groups.map((g) => g.members)).toEqual([
      ['g1', 'g0'],
      ['g2', 'g3'],
    ]);
    expect(state.marker_level).toEqual({
      current: 3,
      unit: 'per_cluster',
      view_type: 'rank_genes_groups',
      levels: [1, 3],
    });
    expect(state.selection).toMatchObject({
      click: { type: 'row_label', value: 'g1' },
      selected_genes: ['g1'],
      enrich_term_genes: ['g2'],
      crop: { row: null, col: 3 },
    });
  });

  test('values and dot sizes for the reported rows x columns', () => {
    const state = get_clustergram_state(make_viz_state({ visible_height: 20 }));
    // Rows g1, g0 (raw 1, 0) x columns c2, c0, c1 (raw 2, 0, 1).
    expect(state.values.values).toEqual([
      [6, 4, 5],
      [3, 1, 2],
    ]);
    expect(state.values.sizes).toEqual([
      [null, 0.5, null],
      [null, null, null],
    ]);
    expect(
      get_clustergram_state(make_viz_state(), { include_values: false }).values
    ).toBeNull();
  });

  test('without a rendered deck, viewport mode falls back to all displayed', () => {
    const viz_state = { ...make_viz_state(), deck_mat: null };
    expect(visible_world_bounds(viz_state)).toBeNull();
    const state = get_clustergram_state(viz_state);
    expect(state.on_screen_known).toBe(false);
    expect(state.rows.names).toEqual(['g1', 'g0', 'g2', 'g3']);
  });

  test('reports the display mode, dot sizing and focused gene', () => {
    const viz_state = make_viz_state();
    viz_state.mat.viz_mode = 'dotplot';
    viz_state.mat.dot_size_encoded = false;
    viz_state.labels.focused_row_index = 2;
    expect(get_clustergram_state(viz_state).display).toEqual({
      mode: 'dotplot',
      size: 'unit',
      focused_row: 'g2',
    });
    viz_state.mat.viz_mode = 'heatmap';
    expect(get_clustergram_state(viz_state).display.size).toBeNull();
  });

  test('ranked markers per cluster, read without changing the view', () => {
    const viz_state = make_viz_state();
    const state = get_clustergram_state(viz_state, {
      markers: { clusters: ['c0', 'nope'], n: 5 },
    });
    expect(state.marker_ranking).toBe(true);
    expect(state.cluster_markers).toEqual([
      {
        cluster: 'c0',
        found: true,
        genes: [
          { name: 'g3', rank: 1, value: 10, size: null },
          { name: 'g1', rank: 2, value: 4, size: 0.5 },
        ],
      },
      { cluster: 'nope', found: false, genes: [] },
    ]);
    // All clusters by default, capped at n; not requested -> null.
    const all = get_clustergram_state(viz_state, { markers: { n: 1 } });
    expect(all.cluster_markers.map((c) => c.genes.map((g) => g.name))).toEqual([
      ['g3'],
      ['g2'],
    ]);
    expect(get_clustergram_state(viz_state).cluster_markers).toBeNull();
  });

  test('the snapshot is plain JSON', () => {
    const state = get_clustergram_state(make_viz_state());
    expect(JSON.parse(JSON.stringify(state))).toEqual(state);
  });

  test('extra rows asked about are appended, with their values', () => {
    // On screen: g1, g0. Asked about: g3 (off screen), g1 (already shown), nope.
    const state = get_clustergram_state(
      make_viz_state({ visible_height: 20 }),
      { extra_rows: ['g3', 'g1', 'nope'] }
    );
    expect(state.rows.names).toEqual(['g1', 'g0', 'g3']);
    expect(state.rows.added).toEqual(['g3']);
    expect(state.rows.missing).toEqual(['nope']);
    // The selection count is unchanged; the value block covers the added row.
    expect(state.rows.total).toBe(2);
    expect(state.values.values[2]).toEqual([12, 10, 11]);
  });
});

// Setter half: the same keys, validation and model values as Python's
// Clustergram.apply_state.
describe('apply_clustergram_state', () => {
  const { apply_clustergram_state } = load_clustergram_state(DISPLAY);

  const make_model = (values = {}) => {
    const state = { ...values };
    const sets = [];
    return {
      sets,
      get: (key) => state[key] ?? null,
      set: (key, value) => {
        state[key] = value;
        sets.push([key, value]);
      },
      save_changes: jest.fn(),
    };
  };
  const viz_state = {
    row_nodes: [{ name: 'MUC2' }, { name: 'TFF3' }],
  };

  test('sets the model values the controls set, and says what changed', () => {
    const model = make_model();
    const done = apply_clustergram_state(model, viz_state, {
      marker_level: 10,
      mode: 'dotplot',
      size: 'unit',
      focus_gene: 'MUC2',
    });
    expect(done).toEqual([
      'DIM -> 10 markers per cluster',
      'mode -> dotplot',
      'dot size -> UNIT',
      'zoomed to MUC2',
    ]);
    expect(model.sets).toEqual([
      ['rank_dim', 10],
      ['viz_mode', 'dotplot'],
      ['dot_size_encoded', false],
      ['focused_gene', 'MUC2'],
    ]);
    expect(model.save_changes).toHaveBeenCalled();
    expect(
      apply_clustergram_state(model, viz_state, { marker_level: 'all' })
    ).toEqual(['DIM -> all rows']);
  });

  test('re-focusing the same gene zooms to it again', () => {
    const model = make_model({ focused_gene: 'MUC2' });
    apply_clustergram_state(model, viz_state, { focus_gene: 'MUC2' });
    expect(model.sets).toEqual([
      ['focused_gene', ''],
      ['focused_gene', 'MUC2'],
    ]);
  });

  test('validates everything before changing anything', () => {
    const model = make_model();
    for (const bad of [
      { zoom: 2 },
      { marker_level: 'lots' },
      { marker_level: 0 },
      { marker_level: 5, mode: 'pie' },
      { size: 'big' },
      { focus_gene: 'NOPE' },
      { marker_level: 5, categories: 'cell types' },
    ]) {
      expect(() => apply_clustergram_state(model, viz_state, bad)).toThrow();
    }
    expect(model.sets).toEqual([]);
  });

  test('categories go to the manual-category editor', () => {
    const model = make_model();
    const apply = jest.fn(() => 2);
    const done = apply_clustergram_state(
      model,
      viz_state,
      { categories: { values: { 4: 'Goblet', 5: 'Plasma' } } },
      apply
    );
    expect(apply).toHaveBeenCalledWith({
      values: { 4: 'Goblet', 5: 'Plasma' },
    });
    expect(done).toEqual(['labeled 2 columns']);
  });
});

test('navigation snapshots round-trip independently of the capped evidence window', () => {
  const {
    get_clustergram_state,
    get_clustergram_controls,
    apply_clustergram_state,
  } = load_clustergram_state(DISPLAY);
  const state = make_viz_state();
  state.mat.orders = {
    row: { clust: [3, 4, 2, 1], rank: [1, 2, 3, 4] },
    col: { rank: [2, 1, 3] },
  };
  state.crop = { filter: { row: [0, 2], col: null } };
  state.zoom = {
    zoom_data: { matrix: { pan_x: 12, pan_y: 25, zoom_x: 1, zoom_y: 2 } },
  };
  state.state_controls = {
    crop: (filter) => {
      state.crop.filter = { ...state.crop.filter, ...filter };
    },
    order: (orders) => {
      Object.entries(orders).forEach(([axis, spec]) => {
        if (Array.isArray(spec)) {
          const ranks = Array(spec.length);
          spec.forEach((index, i) => {
            ranks[index] = spec.length - i;
          });
          state.mat.orders[axis].custom = ranks;
        }
        state.order.current[axis] = Array.isArray(spec) ? 'custom' : spec;
      });
    },
    view: (view) => {
      const c = state.zoom.zoom_data.matrix;
      [c.pan_x, c.pan_y] = view.target;
      [c.zoom_x, c.zoom_y] = view.zoom;
    },
  };
  const model = { set: jest.fn(), save_changes: jest.fn() };
  // Complete controls, whatever the observation caps.
  const controls = () => get_clustergram_controls(state);
  const saved = controls();
  apply_clustergram_state(model, state, {
    order: { row: ['g3', 'g2', 'g1', 'g0'] },
    crop: { row: null },
    view: { target: [5, 5], zoom: [0, 0] },
  });
  const custom = controls();
  expect(custom.order.row).toEqual(['g3', 'g2', 'g1', 'g0']);
  // Observations stay bounded: an explicit order is labeled, not listed.
  const observed = get_clustergram_state(state, { max_rows: 1, max_cols: 1 });
  expect(observed.order).toEqual({ col: 'rank' });
  expect(observed.rows.order.name).toBe('custom');
  expect(observed.crop).toEqual({ row: null, col: null });
  expect(observed.view).toEqual(custom.view);
  apply_clustergram_state(model, state, saved);
  expect(controls()).toEqual(saved);
  apply_clustergram_state(model, state, custom);
  expect(controls()).toEqual(custom);
  expect(() =>
    apply_clustergram_state(model, state, {
      marker_level: 25,
      crop: { row: ['absent'] },
    })
  ).toThrow('unknown row');
  expect(model.set).not.toHaveBeenCalled();
});

test('category configuration errors do not change marker level', () => {
  const { apply_clustergram_state } = load_clustergram_state(DISPLAY);
  const model = { set: jest.fn(), save_changes: jest.fn() };
  expect(() =>
    apply_clustergram_state(
      model,
      {},
      { marker_level: 25, categories: { values: { A: 'label' } } },
      () => {
        throw new Error('no manual category');
      }
    )
  ).toThrow('no manual category');
  expect(model.set).not.toHaveBeenCalled();
});
