/* global require */

// Landscape quality-of-life behavior: bar SVG sizing (rare clusters were
// clipped), shift-click cluster multi-select, bar tooltips, keeping the deck.gl
// tooltip inside the widget, and enlarging transcripts while a gene is selected.

const fs = require('fs');
const path = require('path');

const read_stripped = (rel_path) =>
  fs
    .readFileSync(path.join(__dirname, rel_path), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const load = (rel_path, shims, names, extra_args = {}) => {
  const code = `${shims}\n${read_stripped(rel_path)}\nmodule.exports = { ${names.join(', ')} };`;
  const module = { exports: {} };
  new Function('module', 'exports', ...Object.keys(extra_args), code)(
    module,
    module.exports,
    ...Object.values(extra_args)
  );
  return module.exports;
};

const make_observable = (initial) => {
  let value = initial;
  const subscribers = new Set();
  return {
    get: () => value,
    set: (next) => {
      if (value !== next) {
        value = next;
        subscribers.forEach((fn) => fn(value));
      }
    },
    subscribe: (fn) => {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
  };
};

describe('bar plot helpers and shift-click', () => {
  let bar_plot;

  beforeAll(() => {
    // Real selection semantics from cat.js; everything else is a no-op.
    const shims = `
      const update_cat = (cats, cat) => { cats.cat = cat; };
      const update_selected_cats = (cats, next, obs_store) => {
        cats.reset_cat =
          next.length === cats.selected_cats.length &&
          next.every((value, index) => value === cats.selected_cats[index]);
        cats.selected_cats = cats.reset_cat ? [] : next;
        obs_store.selected_cats.set(cats.selected_cats);
      };
      const update_selected_genes = () => {};
      const new_toggle_cell_layer_visibility = () => {};
      const refresh_nbhd_cloud_cluster_cells = async () => {};
      const refresh_nbhd_cloud_gene_cells = async () => {};
      const apply_nbhd_cloud_slice_filter = () => {};
      const select_nbhd_cloud_gene = async () => {};
      const toggle_nbhd_cloud_cluster_selection = () => {};
      const toggle_trx_layer_visibility = () => {};
      const update_cell_exp_array = () => {};
      const toggle_slider = () => {};
      const refresh_layer = () => {};
      const register_ui_cleanup = () => {};
      const make_gene_hover_tooltip = () => ({});
      const escape_html = (value) => String(value ?? '').replace(/</g, '&lt;');
    `;
    bar_plot = load('../ui/bar_plot.js', shims, [
      'bar_svg_height',
      'toggle_bar_name',
      'cluster_bar_tooltip_html',
      'bar_callback_cat',
    ]);
  });

  it('sizes the SVG so the last bar is not clipped', () => {
    // Bars sit at 16 * i + 2 and are 15px tall, so the last ends at 16n + 1.
    [1, 14, 15, 28, 100].forEach((n) => {
      const last_bar_bottom = 16 * (n - 1) + 2 + 15;
      expect(bar_plot.bar_svg_height(n)).toBeGreaterThanOrEqual(
        last_bar_bottom
      );
    });
  });

  it('toggles a name in or out of a selection', () => {
    expect(bar_plot.toggle_bar_name([], '3')).toEqual(['3']);
    expect(bar_plot.toggle_bar_name(['3'], '7')).toEqual(['3', '7']);
    expect(bar_plot.toggle_bar_name(['3', '7'], '3')).toEqual(['7']);
    expect(bar_plot.toggle_bar_name(['3'], 3)).toEqual([]);
  });

  it('describes a cluster bar with its cell count and the shift hint', () => {
    const html = bar_plot.cluster_bar_tooltip_html(
      { name: '25', value: 1234 },
      { multi_select: true }
    );
    expect(html).toContain('cluster: 25');
    expect(html).toContain('cells: 1,234');
    expect(html).toContain('Shift-click');
    expect(
      bar_plot.cluster_bar_tooltip_html({ name: '<b>', value: 1 })
    ).not.toContain('Shift-click');
  });

  const make_viz_state = (overrides = {}) => {
    const bars = { selectAll: () => ({ style: () => {} }) };
    return {
      cats: { cat: 'cluster', selected_cats: [], svg_bar_cluster: bars },
      genes: { svg_bar_gene: bars },
      sliders: {},
      nbhd: {},
      obs_store: {
        deck_check: make_observable({}),
        selected_cats: make_observable([]),
      },
      ...overrides,
    };
  };

  const click = (viz_state, name, shiftKey = false) =>
    bar_plot.bar_callback_cat({ shiftKey }, { name }, null, {}, viz_state);

  it('replaces the selection on a plain click and clears on re-click', () => {
    const viz_state = make_viz_state();
    click(viz_state, '1');
    click(viz_state, '2');
    expect(viz_state.cats.selected_cats).toEqual(['2']);
    click(viz_state, '2');
    expect(viz_state.cats.selected_cats).toEqual([]);
  });

  it('adds and removes clusters with shift-click', () => {
    const viz_state = make_viz_state();
    click(viz_state, '1');
    click(viz_state, '5', true);
    click(viz_state, '9', true);
    expect(viz_state.cats.selected_cats).toEqual(['1', '5', '9']);
    click(viz_state, '5', true);
    expect(viz_state.cats.selected_cats).toEqual(['1', '9']);
    click(viz_state, '1', true);
    click(viz_state, '9', true);
    expect(viz_state.cats.selected_cats).toEqual([]);
  });

  it('starts a fresh cluster selection when a gene is selected', () => {
    const viz_state = make_viz_state();
    viz_state.cats.cat = 'NPHS2';
    viz_state.cats.selected_cats = ['NPHS2'];
    click(viz_state, '16', true);
    expect(viz_state.cats.selected_cats).toEqual(['16']);
  });

  it('keeps Yearbook cluster clicks single-select', () => {
    const viz_state = make_viz_state({ yearbook: {} });
    click(viz_state, '1');
    click(viz_state, '5', true);
    expect(viz_state.cats.selected_cats).toEqual(['5']);
  });
});

describe('fit_tooltip_in_bounds', () => {
  let fit_tooltip_in_bounds;

  beforeAll(() => {
    const shims = `
      const escape_html = (value) => String(value ?? '');
      const gene_info_tooltip_html = () => '';
      const refresh_gene_tooltip_async = () => {};
      const get_point_cloud_source_index = () => -1;
      const has_uniprot_info = () => true;
    `;
    ({ fit_tooltip_in_bounds } = load('../deck-gl/utils/tooltips.js', shims, [
      'fit_tooltip_in_bounds',
    ]));
  });

  // The tooltip's rect follows its translate(x, y) plus a 50px margin-top,
  // inside a widget whose top-left is at (0, 0).
  const make_tooltip = (width, height) => {
    const tooltip = document.createElement('div');
    tooltip.style.marginTop = '50px';
    tooltip.getBoundingClientRect = () => {
      const [, x, y] = tooltip.style.transform.match(
        /translate\((-?[\d.]+)px, (-?[\d.]+)px\)/
      );
      const left = Number(x);
      const top = Number(y) + 50;
      return {
        left,
        top,
        right: left + width,
        bottom: top + height,
        width,
        height,
      };
    };
    return tooltip;
  };
  const bounds = {
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: 800,
      bottom: 600,
      width: 800,
      height: 600,
    }),
  };
  const position = (tooltip) => tooltip.getBoundingClientRect();

  it('leaves a tooltip that already fits where deck put it', () => {
    const tooltip = make_tooltip(200, 100);
    fit_tooltip_in_bounds(tooltip, 100, 100, bounds);
    expect(position(tooltip)).toMatchObject({ left: 100, top: 150 });
  });

  it('flips left of the cursor near the right edge', () => {
    const tooltip = make_tooltip(260, 100);
    fit_tooltip_in_bounds(tooltip, 700, 100, bounds);
    const rect = position(tooltip);
    expect(rect.right).toBeLessThanOrEqual(700);
    expect(rect.left).toBeGreaterThanOrEqual(0);
  });

  it('flips above the cursor near the bottom edge', () => {
    const tooltip = make_tooltip(200, 150);
    fit_tooltip_in_bounds(tooltip, 100, 520, bounds);
    const rect = position(tooltip);
    expect(rect.bottom).toBeLessThanOrEqual(520);
    expect(rect.top).toBeGreaterThanOrEqual(0);
  });

  it('clamps inside the widget when there is no room to flip', () => {
    const tooltip = make_tooltip(260, 400);
    fit_tooltip_in_bounds(tooltip, 790, 300, bounds);
    const rect = position(tooltip);
    expect(rect.left).toBeGreaterThanOrEqual(0);
    expect(rect.right).toBeLessThanOrEqual(800);
    expect(rect.top).toBeGreaterThanOrEqual(0);
    expect(rect.bottom).toBeLessThanOrEqual(600);
  });
});

describe('cell tooltip expression', () => {
  let cell_expression_html;

  beforeAll(() => {
    const shims = `
      const escape_html = (value) => String(value ?? '');
      const gene_info_tooltip_html = () => '';
      const refresh_gene_tooltip_async = () => {};
      const get_point_cloud_source_index = () => -1;
      const has_uniprot_info = () => true;
      const is_cluster_color_mode = (cats) => !cats.cat || cats.cat === 'cluster';
    `;
    ({ cell_expression_html } = load('../deck-gl/utils/tooltips.js', shims, [
      'cell_expression_html',
    ]));
  });

  const make_cats = (overrides = {}) => ({
    cat: 'CD3E',
    cell_exp_genes: ['CD3E'],
    cell_exp_raw: new Float64Array([0, 4, 2.5]),
    ...overrides,
  });

  test('reports the selected gene expression of the hovered cell', () => {
    expect(cell_expression_html(make_cats(), 1)).toBe('<div>CD3E: 4</div>');
    expect(cell_expression_html(make_cats(), 0)).toBe('<div>CD3E: 0</div>');
  });

  test('labels summed genes and rounds non-integer values', () => {
    const cats = make_cats({
      cat: 'CD3E + CD3D',
      cell_exp_genes: ['CD3E', 'CD3D'],
    });

    expect(cell_expression_html(cats, 2)).toBe('<div>CD3E + CD3D: 2.50</div>');
  });

  test('is empty when cells are colored by cluster or the cell is unknown', () => {
    expect(cell_expression_html(make_cats({ cat: 'cluster' }), 1)).toBe('');
    expect(cell_expression_html(make_cats(), undefined)).toBe('');
  });
});

describe('ini_selected_gene_trx_focus', () => {
  let sliders;
  const radius_calls = [];

  beforeAll(() => {
    const shims = `
      const update_trx_layer_radius = (layers_obj, radius) => { radius_calls.push(radius); };
      const refresh_layer = () => {};
      const register_ui_cleanup = (viz_state, fn) => { viz_state.cleanup = fn; };
      const get_point_cloud_cell_radius = () => 1;
      const update_cell_layer_radius = () => {};
      const update_opacity_single_image_layer = () => {};
      const update_nbhd_cloud_gene_fill_opacity = () => {};
      const update_nbhd_cloud_manual_fill_opacity = () => {};
      const update_nbhd_layer_opacity = () => {};
      const is_orbit_technology = () => false;
      const refresh_cell_layer_data = () => {};
      const rescale_cell_exp_array = () => {};
      const sync_trx_slider = () => {};
      const update_expression_note = () => {};
      const is_trx_force_shown = (viz_state) =>
        viz_state.trx_zone === 'forceable' && Boolean(viz_state.trx_forced);
      const trx_forced_size_scale = () => 3;
      const has_gene_selection = (viz_state) =>
        (viz_state.genes?.selected_genes ?? []).length > 0;
    `;
    sliders = load(
      '../ui/sliders.js',
      shims,
      [
        'ini_selected_gene_trx_focus',
        'ini_trx_slider_modes',
        'sync_trx_slider_range',
        'trx_slider_callback',
        'TRX_FOCUS_SLIDER_VALUE',
      ],
      { radius_calls }
    );
  });

  beforeEach(() => {
    jest.useFakeTimers();
    radius_calls.length = 0;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const setup = (initial_value = 30) => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = '0';
    slider.max = '100';
    slider.value = String(initial_value);
    const viz_state = {
      sliders: { trx: slider },
      obs_store: { selected_genes: make_observable([]) },
    };
    sliders.ini_selected_gene_trx_focus(null, { trx_layer: {} }, viz_state);
    return { slider, viz_state };
  };

  it('grows transcripts to full size on select and restores on clear', () => {
    const { slider, viz_state } = setup(30);

    viz_state.obs_store.selected_genes.set(['NPHS2']);
    jest.advanceTimersByTime(500);
    expect(Number(slider.value)).toBe(sliders.TRX_FOCUS_SLIDER_VALUE);
    expect(radius_calls.at(-1)).toBeCloseTo(1.0);

    // Switching genes keeps the focus size.
    viz_state.obs_store.selected_genes.set(['NPHS1']);
    jest.advanceTimersByTime(500);
    expect(Number(slider.value)).toBe(sliders.TRX_FOCUS_SLIDER_VALUE);

    // Clearing jumps straight back: no frames needed, no intermediate sizes.
    const calls_before_clear = radius_calls.length;
    viz_state.obs_store.selected_genes.set([]);
    expect(Number(slider.value)).toBe(30);
    expect(radius_calls.length).toBe(calls_before_clear + 1);
    expect(radius_calls.at(-1)).toBeCloseTo(0.3);
    jest.advanceTimersByTime(500);
    expect(radius_calls.length).toBe(calls_before_clear + 1);
  });

  it('animates through intermediate sizes', () => {
    const { viz_state } = setup(20);
    viz_state.obs_store.selected_genes.set(['CLU']);
    jest.advanceTimersByTime(500);
    expect(radius_calls.some((radius) => radius > 0.2 && radius < 1.0)).toBe(
      true
    );
  });

  it('stops animating when the user drags the slider', () => {
    const { slider, viz_state } = setup(20);
    viz_state.obs_store.selected_genes.set(['CLU']);
    jest.advanceTimersByTime(50);
    slider.value = '60';
    slider.dispatchEvent(new Event('input'));
    const calls_after_drag = radius_calls.length;
    jest.advanceTimersByTime(500);
    expect(radius_calls.length).toBe(calls_after_drag);
    expect(Number(slider.value)).toBe(60);
  });

  it('does nothing for neighborhood-cloud, which repurposes the slider', () => {
    const slider = document.createElement('input');
    slider.value = '30';
    const viz_state = {
      sliders: { trx: slider },
      nbhd_cloud: { is_nbhd_cloud: true },
      obs_store: { selected_genes: make_observable([]) },
    };
    sliders.ini_selected_gene_trx_focus(null, { trx_layer: {} }, viz_state);
    viz_state.obs_store.selected_genes.set(['CLU']);
    jest.advanceTimersByTime(500);
    expect(slider.value).toBe('30');
    expect(radius_calls).toHaveLength(0);
  });

  it('keeps separate size and opacity positions as the view changes', () => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.value = '30';
    const viz_state = {
      close_up: true,
      cats: {},
      sliders: { trx: slider },
      obs_store: {
        close_up: make_observable(true),
        selected_genes: make_observable([]),
        selected_cats: make_observable([]),
      },
    };
    const layers_obj = { trx_layer: { props: { visible: true } } };
    sliders.ini_trx_slider_modes(layers_obj, viz_state);
    expect(viz_state.trx_slider_mode).toBe('size');

    viz_state.obs_store.close_up.set(false);
    expect(viz_state.trx_slider_mode).toBe('opacity');
    expect(slider.value).toBe('100');
    slider.value = '40';

    viz_state.obs_store.close_up.set(true);
    expect(slider.value).toBe('30');
    viz_state.obs_store.close_up.set(false);
    expect(slider.value).toBe('40');
  });

  it('applies the gene-focus size directly while zoomed out', () => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.value = '40';
    const viz_state = {
      trx_slider_mode: 'opacity',
      trx_slider_values: { size: 30, opacity: 40 },
      sliders: { trx: slider },
      obs_store: { selected_genes: make_observable([]) },
    };
    sliders.ini_selected_gene_trx_focus(null, { trx_layer: {} }, viz_state);
    viz_state.obs_store.selected_genes.set(['UMOD']);
    expect(viz_state.trx_slider_values.size).toBe(
      sliders.TRX_FOCUS_SLIDER_VALUE
    );
    expect(slider.value).toBe('40');
    expect(radius_calls.at(-1)).toBeCloseTo(1.0);

    viz_state.obs_store.selected_genes.set([]);
    expect(viz_state.trx_slider_values.size).toBe(30);
  });

  it('allows larger transcripts while forced, and shrinks them after', () => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.max = '100';
    slider.value = '100';
    const viz_state = {
      trx_slider_mode: 'size',
      trx_zone: 'forceable',
      trx_forced: true,
      sliders: { trx: slider },
    };
    const layers_obj = { trx_layer: {} };

    sliders.sync_trx_slider_range(layers_obj, viz_state);
    expect(slider.max).toBe('300');
    expect(slider.value).toBe('100');
    expect(radius_calls).toHaveLength(0);

    slider.value = '300';
    viz_state.trx_zone = 'auto';
    sliders.sync_trx_slider_range(layers_obj, viz_state);
    expect(slider.max).toBe('100');
    expect(slider.value).toBe('100');
    expect(radius_calls.at(-1)).toBeCloseTo(1.0);
  });

  it('scales cell opacity only while the slider shows it', () => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.value = '30';
    const viz_state = {
      close_up: false,
      cats: { cat: 'UMOD' },
      sliders: { trx: slider },
      obs_store: {
        close_up: make_observable(false),
        selected_genes: make_observable([]),
        selected_cats: make_observable([]),
      },
    };
    const layers_obj = { trx_layer: { props: { visible: true } } };
    sliders.ini_trx_slider_modes(layers_obj, viz_state);

    // Zoomed out: full opacity at 40% of the max.
    slider.value = '40';
    sliders.trx_slider_callback(null, layers_obj, viz_state);
    expect(viz_state.cats.cell_exp_scale).toBe(0.4);

    // Close-up cells use the full range...
    viz_state.obs_store.close_up.set(true);
    expect(viz_state.cats.cell_exp_scale).toBe(1);

    // ...and zooming back out restores the setting.
    viz_state.obs_store.close_up.set(false);
    expect(slider.value).toBe('40');
    expect(viz_state.cats.cell_exp_scale).toBe(0.4);
  });

  it('uses the forced size range when entering close-up forced', () => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.value = '30';
    const viz_state = {
      close_up: false,
      trx_zone: 'forceable',
      trx_forced: true,
      cats: {},
      sliders: { trx: slider },
      obs_store: {
        close_up: make_observable(false),
        selected_genes: make_observable([]),
        selected_cats: make_observable([]),
      },
    };
    const layers_obj = { trx_layer: { props: { visible: true } } };
    sliders.ini_trx_slider_modes(layers_obj, viz_state);
    expect(slider.max).toBe('100');

    viz_state.obs_store.close_up.set(true);
    expect(slider.max).toBe('300');
    expect(slider.value).toBe('30');
  });

  // A Landscape's TRX slider at intermediate zoom: forced transcripts widen
  // the size range, and its top is full size.
  const make_landscape = ({ close_up, trx_zone, trx_forced }) => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.value = '30';
    const viz_state = {
      close_up,
      trx_zone,
      trx_forced,
      cats: {},
      genes: { selected_genes: [] },
      sliders: { trx: slider },
      obs_store: {
        close_up: make_observable(close_up),
        selected_genes: make_observable([]),
        selected_cats: make_observable([]),
      },
    };
    const layers_obj = { trx_layer: { props: { visible: true } } };
    sliders.ini_trx_slider_modes(layers_obj, viz_state);
    sliders.ini_selected_gene_trx_focus(null, layers_obj, viz_state);
    const select = (genes) => {
      viz_state.genes.selected_genes = genes;
      viz_state.obs_store.selected_genes.set(genes);
    };
    return { slider, viz_state, layers_obj, select };
  };

  it('slides to the top of the wider range at intermediate zoom', () => {
    const { slider, select } = make_landscape({
      close_up: true,
      trx_zone: 'forceable',
      trx_forced: true,
    });
    expect(slider.max).toBe('300');

    select(['NPHS2']);
    jest.advanceTimersByTime(500);
    expect(slider.value).toBe('300');
    expect(radius_calls.at(-1)).toBeCloseTo(3.0);

    select([]);
    expect(slider.value).toBe('30');
    expect(radius_calls.at(-1)).toBeCloseTo(0.3);
  });

  it('keeps selected genes at full size as intermediate zoom starts and ends', () => {
    const { slider, viz_state, layers_obj, select } = make_landscape({
      close_up: true,
      trx_zone: 'auto',
      trx_forced: true,
    });
    select(['UMOD']);
    jest.advanceTimersByTime(500);
    expect(slider.value).toBe('100');

    viz_state.trx_zone = 'forceable';
    sliders.sync_trx_slider_range(layers_obj, viz_state);
    expect(slider.value).toBe('300');
    expect(radius_calls.at(-1)).toBeCloseTo(3.0);

    viz_state.trx_zone = 'auto';
    sliders.sync_trx_slider_range(layers_obj, viz_state);
    expect(slider.value).toBe('100');
    expect(radius_calls.at(-1)).toBeCloseTo(1.0);

    // A smaller size the user picked is kept.
    slider.value = '60';
    viz_state.trx_zone = 'forceable';
    sliders.sync_trx_slider_range(layers_obj, viz_state);
    expect(slider.value).toBe('60');
  });

  it('loads transcripts for already-selected genes at full size', () => {
    const { slider, viz_state, select } = make_landscape({
      close_up: false,
      trx_zone: 'forceable',
      trx_forced: false,
    });
    // Zoomed out, the selection sets full close-up size directly.
    select(['UMOD']);
    expect(viz_state.trx_slider_values.size).toBe(
      sliders.TRX_FOCUS_SLIDER_VALUE
    );

    // Clicking TRX.
    viz_state.trx_forced = true;
    viz_state.obs_store.close_up.set(true);
    expect(slider.max).toBe('300');
    expect(slider.value).toBe('300');
    expect(radius_calls.at(-1)).toBeCloseTo(3.0);

    select([]);
    expect(slider.value).toBe('30');
  });

  it('restores a size from the wider range within the close-up range', () => {
    const { slider, viz_state, layers_obj, select } = make_landscape({
      close_up: true,
      trx_zone: 'forceable',
      trx_forced: true,
    });
    slider.value = '250';
    select(['UMOD']);
    jest.advanceTimersByTime(500);

    // Zooming out past intermediate zoom, then clearing the selection.
    viz_state.trx_zone = 'far';
    viz_state.trx_forced = false;
    sliders.sync_trx_slider_range(layers_obj, viz_state);
    viz_state.obs_store.close_up.set(false);
    select([]);
    expect(viz_state.trx_slider_values.size).toBe(100);
    expect(radius_calls.at(-1)).toBeCloseTo(1.0);
  });
});
