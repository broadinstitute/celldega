/* global require */

// Enrich-linked row-label styling: term genes render blue (#2f74ff), the
// focused gene gets a one-datum bold overlay, and focus_matrix_row flies the
// views to the row instead of snapping.

const fs = require('fs');
const path = require('path');

const strip_modules = (source) =>
  source
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ')
    .replace(/^export function /gm, 'function ');

const load_module = (relative_path, shims, exports_expr) => {
  const source = strip_modules(
    fs.readFileSync(path.join(__dirname, relative_path), 'utf8')
  );
  const code = `${shims}\n${source}\nmodule.exports = ${exports_expr};`;
  const module = { exports: {} };
  new Function('module', 'exports', code)(module, module.exports);
  return module.exports;
};

const layer_shims = `
  class TextLayer {
    constructor(props) {
      this.props = props;
      this.id = props.id;
    }
    clone(next = {}) {
      return new TextLayer({ ...this.props, ...next });
    }
  }
  const d3 = { easeCubic: (t) => t };
  const crop_filter_signature = () => 0;
  const crop_fade_axis_alpha_factor = () => 1;
  const filter_label_data = (viz_state) => viz_state.labels.row_label_data;
  const get_axis_label_font_size = () => 10;
  const get_zoomed_axis_label_font_size = () => 10;
  const get_axis_center_position = () => 0;
  const get_axis_display_count = () => 2;
  const composition_row_label_position = () => [50, 0];
  const get_layer_update_triggers = (layer) => layer.props.updateTriggers || {};
  const get_mat_layers_list = (layers_mat) =>
    [layers_mat.row_label_layer, layers_mat.row_label_focus_layer].filter(
      Boolean
    );
  const row_label_color_triggers = (viz_state) => [
    0,
    0,
    viz_state.labels._row_vis_rev || 0,
    viz_state.labels._row_style_rev || 0,
    viz_state.order?.current?.col,
  ];
  const col_label_color_triggers = (viz_state) => [
    0,
    0,
    viz_state.labels._col_style_rev || 0,
    viz_state.order?.current?.row,
  ];
  const mat_reorder_triggers = () => ({});
  const deselect_reorder_buttons = () => {};
  const refresh_row_label_visibility = () => {};
  const refresh_composition_dendro = () => {};
  const toggle_dendro_layer_visibility = () => {};
`;

const make_viz_state = (overrides = {}) => ({
  mat: { viz_mode: 'heatmap' },
  animate: { duration: 100 },
  zoom: { zoom_data: { matrix: { zoom_y: 0 } } },
  order: { current: { row: 'clust', col: 'clust' } },
  labels: {
    highlighted_genes: new Set(),
    row_visibility: null,
    _row_vis_rev: 0,
    _row_style_rev: 0,
    _col_style_rev: 0,
    focused_row_index: null,
    reorder_driver: null,
    row_label_data: [
      { name: 'EPHA7', index: 0 },
      { name: 'FAM124A', index: 1 },
    ],
    ...overrides.labels,
  },
  ...overrides,
});

describe('term-gene row label highlighting', () => {
  let ini_row_label_layer;
  let ini_col_label_layer;
  let ini_row_label_focus_layer;
  let refresh_row_label_highlight;
  let handle_label_click;

  beforeAll(() => {
    ({
      ini_row_label_layer,
      ini_col_label_layer,
      ini_row_label_focus_layer,
      refresh_row_label_highlight,
      handle_label_click,
    } = load_module(
      '../deck-gl/matrix/label_layers.js',
      layer_shims,
      '{ ini_row_label_layer, ini_col_label_layer, ini_row_label_focus_layer, refresh_row_label_highlight, handle_label_click }'
    ));
  });

  test('labels for term genes are blue, matched case-insensitively', () => {
    const viz_state = make_viz_state();
    viz_state.labels.highlighted_genes = new Set(['epha7']);

    const layer = ini_row_label_layer(viz_state);
    expect(layer.props.getColor({ name: 'EPHA7', index: 0 })).toEqual([
      47, 116, 255, 255,
    ]);
    expect(layer.props.getColor({ name: 'FAM124A', index: 1 })).toEqual([
      0, 0, 0, 255,
    ]);
  });

  test('composition-mode visibility still hides highlighted labels', () => {
    const viz_state = make_viz_state({ mat: { viz_mode: 'composition' } });
    viz_state.labels.highlighted_genes = new Set(['epha7', 'fam124a']);
    viz_state.labels.row_visibility = [true, false];

    const layer = ini_row_label_layer(viz_state);
    expect(layer.props.getColor({ name: 'EPHA7', index: 0 })).toEqual([
      47, 116, 255, 255,
    ]);
    expect(layer.props.getColor({ name: 'FAM124A', index: 1 })).toEqual([
      0, 0, 0, 0,
    ]);
  });

  test('focus overlay holds only the focused row, bold, and forwards picking', () => {
    const viz_state = make_viz_state();
    viz_state.labels.focused_row_index = 1;

    const layer = ini_row_label_focus_layer(viz_state);
    expect(layer.id).toBe('row-label-layer-focus');
    expect(layer.id.includes('row-label-layer')).toBe(true);
    expect(layer.props.data).toEqual([{ name: 'FAM124A', index: 1 }]);
    expect(layer.props.fontWeight).toBe('bold');

    // The overlay replaces the (transparent, unpickable) base label, so it
    // must be pickable itself and forward clicks to the base handler.
    expect(layer.props.pickable).toBe(true);
    const clicks = [];
    viz_state.labels._row_label_click_handler = (event) => clicks.push(event);
    layer.props.onClick({ object: { name: 'FAM124A', index: 1 } });
    expect(clicks).toHaveLength(1);

    viz_state.labels.focused_row_index = null;
    expect(ini_row_label_focus_layer(viz_state).props.data).toEqual([]);
  });

  test("the focused row's base label hides under the bold overlay", () => {
    const viz_state = make_viz_state();
    viz_state.labels.focused_row_index = 0;

    const layer = ini_row_label_layer(viz_state);
    expect(layer.props.getColor({ name: 'EPHA7', index: 0 })).toEqual([
      0, 0, 0, 0,
    ]);
    expect(layer.props.getColor({ name: 'FAM124A', index: 1 })).toEqual([
      0, 0, 0, 255,
    ]);
  });

  test('the double-clicked reorder driver is blue while its custom order holds', () => {
    const viz_state = make_viz_state();
    viz_state.order = { current: { row: 'custom', col: 'clust' } };
    viz_state.labels.reorder_driver = { axis: 'col', name: 'S1', index: 0 };

    const col_layer = ini_col_label_layer(viz_state);
    expect(col_layer.props.getColor({ name: 'S1', index: 0 })).toEqual([
      47, 116, 255, 255,
    ]);
    expect(col_layer.props.getColor({ name: 'S2', index: 1 })).toEqual([
      0, 0, 0, 255,
    ]);

    // A button reorder replaces the custom order → the driver reverts.
    viz_state.order.current.row = 'clust';
    expect(col_layer.props.getColor({ name: 'S1', index: 0 })).toEqual([
      0, 0, 0, 255,
    ]);

    // Row-label drivers work the same way (they custom-sort the columns).
    viz_state.order.current.col = 'custom';
    viz_state.labels.reorder_driver = { axis: 'row', name: 'EPHA7', index: 0 };
    const row_layer = ini_row_label_layer(viz_state);
    expect(row_layer.props.getColor({ name: 'EPHA7', index: 0 })).toEqual([
      47, 116, 255, 255,
    ]);
  });

  test('a column double-click reorders AND sends the top genes (row skips the send)', () => {
    jest.useFakeTimers();
    const viz_state = make_viz_state({
      mat: {
        viz_mode: 'heatmap',
        net_mat: [
          [5, 1],
          [2, 7],
        ],
        orders: { row: {}, col: {} },
      },
    });
    const make_layer = (id) => ({
      id,
      props: {},
      clone(props = {}) {
        return { ...this, props: { ...this.props, ...props } };
      },
    });
    const layers_mat = {
      mat_layer: make_layer('mat-layer'),
      row_label_layer: make_layer('row-label-layer'),
      col_label_layer: make_layer('col-label-layer'),
      row_cat_layer: make_layer('row-layer'),
      col_cat_layer: make_layer('col-layer'),
    };
    const deck_mat = { setProps: () => {} };
    const single_clicks = [];
    const callback = (label) => single_clicks.push(label);
    const event = { object: { name: 'S1', index: 0 } };

    // Two clicks within the double-click window on the same column label.
    handle_label_click(event, deck_mat, layers_mat, viz_state, 'col', callback);
    handle_label_click(event, deck_mat, layers_mat, viz_state, 'col', callback);

    expect(single_clicks).toEqual([{ name: 'S1', index: 0 }]);
    expect(viz_state.order.current.row).toBe('custom');
    expect(viz_state.labels.reorder_driver).toEqual({
      axis: 'col',
      name: 'S1',
      index: 0,
    });

    // A row double-click reorders without firing the single-click sync.
    handle_label_click(event, deck_mat, layers_mat, viz_state, 'row', callback);
    handle_label_click(event, deck_mat, layers_mat, viz_state, 'row', callback);
    expect(single_clicks).toHaveLength(1);
    expect(viz_state.order.current.col).toBe('custom');

    jest.useRealTimers();
  });

  test('focus overlay never transitions (no flight from the previous focus, no per-character truncation)', () => {
    const viz_state = make_viz_state();
    viz_state.labels.focused_row_index = 0;

    const layer = ini_row_label_focus_layer(viz_state);
    expect(layer.props.transitions).toBeUndefined();
  });

  test('refresh_row_label_highlight bumps the style revision into triggers', () => {
    const viz_state = make_viz_state();
    const layers_mat = {
      row_label_layer: ini_row_label_layer(viz_state),
      row_label_focus_layer: ini_row_label_focus_layer(viz_state),
    };
    const set_props_calls = [];
    const deck_mat = { setProps: (props) => set_props_calls.push(props) };

    viz_state.labels.highlighted_genes = new Set(['epha7']);
    refresh_row_label_highlight(deck_mat, layers_mat, viz_state);

    expect(viz_state.labels._row_style_rev).toBe(1);
    expect(layers_mat.row_label_layer.props.updateTriggers.getColor).toContain(
      1
    );
    expect(set_props_calls).toHaveLength(1);
    expect(set_props_calls[0].layers).toContain(
      layers_mat.row_label_focus_layer
    );
  });
});

describe('animated focus zoom', () => {
  let focus_matrix_row;
  let with_focus_zoom_transitions;
  let recorded;

  beforeAll(() => {
    const row_search_shims = `
      class LinearInterpolator {
        constructor(opts) {
          this.opts = opts;
        }
      }
      const d3 = { easeCubic: (t) => t };
      const composition_row_label_position = () => [50, 7];
      const get_axis_center_position = () => 42;
      const get_axis_display_count = (viz_state, axis) =>
        axis === 'row' ? viz_state.mat.num_rows : viz_state.mat.num_cols;
      const get_zoomed_axis_label_font_size = () => 10;
      const curate_pan_x = (x) => x;
      const curate_pan_y = (y) => y;
      const refresh_row_label_styles = (layers_mat) => {
        layers_mat.row_label_focus_layer = { id: 'row-label-layer-focus' };
      };
      const get_mat_layers_list = () => [];
      const redefine_global_view_state = (viz_state, viewId, zoom, pan) => ({
        matrix: { zoom, target: pan },
        rows: { zoom, target: pan },
      });
      const ini_views = () => {};
      const update_zoom_data = () => {};
    `;
    ({ focus_matrix_row, with_focus_zoom_transitions } = load_module(
      '../deck-gl/matrix/row_search.js',
      row_search_shims,
      '{ focus_matrix_row, with_focus_zoom_transitions, FOCUS_ZOOM_TRANSITION_MS }'
    ));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('every view state gets the same fly-to transition', () => {
    const animated = with_focus_zoom_transitions({
      matrix: { zoom: [1, 2], target: [3, 4] },
      rows: { zoom: [0, 2], target: [5, 4] },
    });

    Object.values(animated).forEach((view_state) => {
      expect(view_state.transitionDuration).toBe(750);
      expect(view_state.transitionInterpolator.opts).toEqual({
        transitionProps: ['target', 'zoom'],
      });
      expect(typeof view_state.transitionEasing).toBe('function');
    });
    expect(animated.matrix.zoom).toEqual([1, 2]);
  });

  test('focus_matrix_row animates, bolds the row, and guards the transition window', () => {
    jest.useFakeTimers();
    recorded = [];
    const deck_mat = { setProps: (props) => recorded.push(props) };
    const layers_mat = {
      row_label_layer: { clone: () => ({ clone: () => ({}) }) },
      col_label_layer: { clone: () => ({ clone: () => ({}) }) },
    };
    const viz_state = {
      mat: { viz_mode: 'heatmap', num_rows: 100, num_cols: 10 },
      zoom: {
        ini_zoom_x: 0,
        zoom_delay: 0,
        zoom_data: {
          matrix: { zoom_x: 0, zoom_y: 0, pan_x: 0, pan_y: 0 },
          total_zoom: { x: 0, y: 0 },
        },
      },
      labels: {},
      views: { views_list: [] },
    };

    const focused = focus_matrix_row(deck_mat, layers_mat, viz_state, 3);

    expect(focused).toBe(true);
    expect(viz_state.labels.focused_row_index).toBe(3);
    expect(layers_mat.row_label_focus_layer).toEqual({
      id: 'row-label-layer-focus',
    });
    expect(viz_state.zoom._programmatic_view_transition).toBe(true);

    const { viewState } = recorded[0];
    expect(viewState.matrix.transitionDuration).toBe(750);
    expect(viewState.rows.transitionDuration).toBe(750);

    jest.advanceTimersByTime(750 + 200);
    expect(viz_state.zoom._programmatic_view_transition).toBe(false);
  });
});

describe('on_view_state_change during a programmatic transition', () => {
  let on_view_state_change;

  beforeAll(() => {
    const view_state_shims = `
      class OrthographicView {
        constructor(props) {
          this.props = props;
        }
      }
      const refresh_row_label_visibility = () => {};
      const get_zoomed_axis_label_font_size = () => 10;
      const curate_pan_x = (x) => x;
      const curate_pan_y = (y) => y;
      const get_mat_layers_list = () => [];
      const redefine_global_view_state = () => ({});
      const update_zoom_data = () => {};
    `;
    ({ on_view_state_change } = load_module(
      '../deck-gl/matrix/on_view_state_change.js',
      view_state_shims,
      '{ on_view_state_change }'
    ));
  });

  const make_fixture = () => {
    const set_props_calls = [];
    const deck_mat = { setProps: (props) => set_props_calls.push(props) };
    const cloneable = { clone: () => cloneable };
    const layers_mat = {
      row_label_layer: cloneable,
      col_label_layer: cloneable,
      row_label_focus_layer: cloneable,
    };
    const viz_state = {
      mat: { viz_mode: 'heatmap' },
      labels: {},
      views: { views_list: [] },
      zoom: {
        _programmatic_view_transition: true,
        major_zoom_axis: 'all',
        minor_zoom_axis: 'none',
        zoom_delay: 0,
        ini_zoom_x: 0,
        ini_zoom_y: 0,
        switch_ratio: 1,
        zoom_data: {
          matrix: { zoom_x: 0, zoom_y: 0, pan_x: 0, pan_y: 0 },
          total_zoom: { x: 0, y: 0 },
        },
      },
      crop: { active: false },
    };
    return { deck_mat, layers_mat, viz_state, set_props_calls };
  };

  const params = (interactionState) => ({
    viewState: { zoom: [1, 1], target: [5, 5] },
    viewId: 'matrix',
    interactionState,
  });

  test('interpolated transition frames are ignored', () => {
    const { deck_mat, layers_mat, viz_state, set_props_calls } = make_fixture();

    on_view_state_change(
      params({ inTransition: true }),
      deck_mat,
      layers_mat,
      viz_state
    );

    expect(set_props_calls).toHaveLength(0);
    expect(viz_state.zoom.zoom_data.total_zoom).toEqual({ x: 0, y: 0 });
  });

  test('user gestures (no inTransition) are still handled', () => {
    const { deck_mat, layers_mat, viz_state, set_props_calls } = make_fixture();

    on_view_state_change(
      params({ isDragging: true }),
      deck_mat,
      layers_mat,
      viz_state
    );

    expect(set_props_calls).toHaveLength(1);
  });
});
