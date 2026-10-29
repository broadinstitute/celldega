/* global require */

// The TRX button click (text_buttons.js): showing transcripts takes over from
// neighborhoods and region editing, whether they load automatically
// (close-up) or are forced at intermediate zoom.

const fs = require('fs');
const path = require('path');

const source = ['../ui/nbhd_button.js', '../ui/text_buttons.js']
  .map((file) =>
    fs
      .readFileSync(path.join(__dirname, file), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ')
  )
  .join('\n');

const calls = [];
const shims = `
  const record = (name) => (...args) => { calls.push([name, ...args]); };
  const d3 = { select: (node) => node };
  const calc_viewport = async () => { calls.push(['calc_viewport']); };
  const new_toggle_cell_layer_visibility = record('cell');
  const toggle_visibility_single_image_layer = record('image');
  const toggle_nbhd_cloud_shapes_layer_visibility = record('nbhd_cloud');
  const toggle_nbhd_layer_visibility = record('nbhd');
  const toggle_path_layer_visibility = record('path');
  const toggle_trx_layer_visibility = record('trx');
  const refresh_composition_dendro = () => {};
  const toggle_dendro_layer_visibility = () => {};
  const col_label_color_triggers = () => {};
  const get_layer_update_triggers = () => {};
  const get_mat_layers_list = () => [];
  const mat_reorder_triggers = () => {};
  const row_label_color_triggers = () => {};
  const refresh_row_label_visibility = () => {};
  const crop_filter_signature = () => '';
  const refresh_layer = () => {};
  const toggle_slider = () => {};
  const sync_trx_button = () => {};
`;
const module_ = { exports: {} };
new Function(
  'module',
  'calls',
  `${shims}\n${source}\nmodule.exports = { trx_button_callback_ist, cell_button_callback };`
)(module_, calls);
const { trx_button_callback_ist, cell_button_callback } = module_.exports;

const make_observable = (initial) => {
  let value = initial;
  return {
    get: () => value,
    set: (next) => {
      value = next;
    },
  };
};

// Minimal d3-selection stand-in that records styles.
const make_styled = (styles = {}) => {
  const node = {
    styles,
    style: (name, value) => {
      if (value === undefined) return styles[name];
      styles[name] = value;
      return node;
    },
  };
  return node;
};

// Neighborhoods and the region editor showing, gene bars dimmed.
const make_viz_state = (trx_zone) => {
  const gene_bars = make_styled({ opacity: 0.2 });
  return {
    trx_zone,
    sliders: { trx: {} },
    nbhd: { is_nbhd: true },
    buttons: { buttons: { nbhd: make_styled({ color: 'blue' }) } },
    genes: { svg_bar_gene: { selectAll: () => gene_bars }, gene_bars },
    obs_store: {
      viz_nbhd_layer: make_observable(true),
      viz_edit_layer: make_observable(true),
      deck_check: make_observable({}),
    },
    last_viewport_params: {},
  };
};

const expect_transcripts_took_over = (viz_state) => {
  expect(calls).toContainEqual(['nbhd', {}, false]);
  expect(viz_state.obs_store.viz_nbhd_layer.get()).toBe(false);
  expect(viz_state.obs_store.viz_edit_layer.get()).toBe(false);
  expect(viz_state.buttons.buttons.nbhd.styles.color).toBe('gray');
  expect(viz_state.genes.gene_bars.styles.opacity).toBe(1);
};

describe('TRX button', () => {
  beforeEach(() => {
    calls.length = 0;
  });

  it('takes over from neighborhoods when forcing at intermediate zoom', async () => {
    const viz_state = make_viz_state('forceable');
    await trx_button_callback_ist({}, {}, {}, viz_state);

    expect(viz_state.trx_forced).toBe(true);
    expect(calls).toContainEqual(['trx', {}, true]);
    expect(calls).toContainEqual(['calc_viewport']);
    expect_transcripts_took_over(viz_state);
  });

  it('leaves neighborhoods alone when un-forcing', async () => {
    const viz_state = make_viz_state('forceable');
    viz_state.trx_forced = true;
    await trx_button_callback_ist({}, {}, {}, viz_state);

    expect(viz_state.trx_forced).toBe(false);
    expect(calls.some(([name]) => name === 'nbhd')).toBe(false);
    expect(viz_state.obs_store.viz_nbhd_layer.get()).toBe(true);
  });

  it('takes over the same way in close-up', async () => {
    const viz_state = make_viz_state('auto');
    const button = make_styled({ color: 'gray' });
    await trx_button_callback_ist({ currentTarget: button }, {}, {}, viz_state);

    expect(button.styles.color).toBe('blue');
    expect(calls).toContainEqual(['trx', {}, true]);
    expect_transcripts_took_over(viz_state);
  });

  it('does nothing too far out', async () => {
    const viz_state = make_viz_state('far');
    await trx_button_callback_ist({}, {}, {}, viz_state);
    expect(calls).toHaveLength(0);
    expect(viz_state.trx_forced).toBeUndefined();
  });
});

describe('CELL after NBHD drawing', () => {
  it('exits editing with cells visible and keeps frontend gate membership highlighted', async () => {
    calls.length = 0;
    const state = make_viz_state('far');
    state.cats = { svg_bar_cluster: { selectAll: () => make_styled() } };
    state.obs_store.selected_cells = make_observable(['a', 'c']);
    state.highlighted_cells = new Set(['a', 'c']);
    const button = make_styled({ color: 'blue' });
    await cell_button_callback({ currentTarget: button }, {}, {}, state);
    expect(calls).toContainEqual(['cell', {}, true]);
    expect(state.obs_store.viz_edit_layer.get()).toBe(false);
    expect(state.obs_store.viz_nbhd_layer.get()).toBe(false);
    expect(state.obs_store.selected_cells.get()).toEqual(['a', 'c']);
    expect([...state.highlighted_cells]).toEqual(['a', 'c']);
    expect(button.styles.color).toBe('blue');
  });
});
