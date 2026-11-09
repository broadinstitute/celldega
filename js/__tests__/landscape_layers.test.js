/* global require */

const load = (shims) => {
  const source = require('fs')
    .readFileSync(
      require('path').join(__dirname, '../viz/landscape_layers.js'),
      'utf8'
    )
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
  return new Function(
    ...Object.keys(shims),
    `${source}; return {
    get_landscape_layers, validate_landscape_layers, apply_landscape_layers
  };`
  )(...Object.values(shims));
};

const observable = (value) => ({
  get: () => value,
  set: (next) => {
    value = next;
  },
});
const slider = (value, name) => {
  const control = { value, name };
  control.apply_value = jest.fn(async (next) => {
    control.value = next;
  });
  return control;
};
const fixture = () => {
  const layers = {
    cell_layer: { props: { visible: true } },
    path_layer: { props: { visible: true } },
    trx_layer: { props: { visible: false } },
    nbhd_layer: { props: { visible: false } },
    image_layers: [
      {
        id: 'DAPI-0',
        props: { imageButtonName: 'DAPI', channelVisible: true, visible: true },
      },
    ],
  };
  const state = {
    layers_obj: layers,
    img: { image_layer_sliders: [slider(50, 'DAPI')], image_source: 'primary' },
    obs_store: {
      viz_image_layers: observable(true),
      viz_background_layer: observable(true),
      viz_nbhd_layer: observable(false),
      viz_edit_layer: observable(false),
    },
    sliders: { cell: slider(50), trx: slider(70), nbhd: slider(25) },
    trx_slider_values: { size: 70, opacity: 90 },
    trx_slider_mode: 'size',
    trx_zone: 'forceable',
    last_viewport_params: { viewState: {} },
  };
  const toggle = (key) =>
    jest.fn((object, visible) => {
      object[key].props.visible = visible;
    });
  const shims = {
    calc_viewport: jest.fn(async () => {}),
    new_toggle_cell_layer_visibility: toggle('cell_layer'),
    toggle_path_layer_visibility: toggle('path_layer'),
    toggle_trx_layer_visibility: toggle('trx_layer'),
    toggle_nbhd_layer_visibility: toggle('nbhd_layer'),
    toggle_visibility_image_layers: jest.fn((object, visible) => {
      object.image_layers.forEach((l) => {
        l.props.visible = visible && l.props.channelVisible;
      });
    }),
    toggle_visibility_single_image_layer: jest.fn((object, name, visible) => {
      object.image_layers
        .filter((l) => l.props.imageButtonName === name)
        .forEach((l) => {
          l.props.channelVisible = visible;
        });
    }),
    get_aligned_he: (img) => img.aligned_he,
    sync_trx_button: jest.fn(),
    trx_forced_size_scale: () => 2,
    toggle_slider: jest.fn(),
    refresh_layer: jest.fn(),
  };
  return {
    state,
    layers,
    shims,
    api: load(shims),
    context: { layers_obj: layers, deck: {} },
  };
};

test('layer controls round trip through render helpers and awaited slider callbacks', async () => {
  const { state, layers, shims, api, context } = fixture();
  const saved = api.get_landscape_layers(state);
  const changes = {
    layers: {
      image: false,
      cells: false,
      transcripts: true,
      neighborhoods: true,
    },
    channels: { DAPI: { visible: false, intensity: 21 } },
    sliders: { cell: 30, nbhd: 80, trx: { size: 120, opacity: 110 } },
  };
  api.validate_landscape_layers(state, changes);
  await api.apply_landscape_layers(state, context, changes);
  expect(api.get_landscape_layers(state)).toMatchObject(changes);
  expect(layers.path_layer.props.visible).toBe(false);
  expect(shims.calc_viewport).toHaveBeenCalledWith(
    state.last_viewport_params,
    context.deck,
    layers,
    state
  );
  expect(state.sliders.trx.apply_value).toHaveBeenCalledWith(120);
  expect(state.sliders.cell.apply_value).toHaveBeenCalledWith(30);
  api.validate_landscape_layers(state, saved);
  await api.apply_landscape_layers(state, context, saved);
  expect(api.get_landscape_layers(state)).toEqual(saved);
  expect(state.trx_forced).toBe(false);
});

test('master image visibility preserves channel choices and is isolated per instance', async () => {
  const a = fixture();
  const b = fixture();
  await a.api.apply_landscape_layers(a.state, a.context, {
    layers: { image: false },
  });
  expect(a.api.get_landscape_layers(a.state).channels.DAPI.visible).toBe(true);
  expect(a.layers.image_layers[0].props.visible).toBe(false);
  expect(b.api.get_landscape_layers(b.state).layers.image).toBe(true);
  await a.api.apply_landscape_layers(a.state, a.context, {
    channels: { DAPI: { visible: false } },
  });
  await a.api.apply_landscape_layers(a.state, a.context, {
    layers: { image: true },
  });
  expect(a.layers.image_layers[0].props.visible).toBe(false);
});

test.each([
  { layers: { cells: 1 } },
  { layers: { typo: true } },
  { channels: { MISSING: { visible: true } } },
  { channels: { DAPI: { intensity: 101 } } },
  { sliders: { cell: -1 } },
  { sliders: { trx: { size: 201 } } },
  { sliders: { trx: { opacity: 151 } } },
  { image_source: 'he' },
])(
  'rejects unavailable or out-of-range controls without mutation: %j',
  (changes) => {
    const { state, api } = fixture();
    const before = api.get_landscape_layers(state);
    expect(() => api.validate_landscape_layers(state, changes)).toThrow();
    expect(api.get_landscape_layers(state)).toEqual(before);
  }
);

test('available H&E source uses the same image mask and updates its control', async () => {
  const { state, layers, api, context, shims } = fixture();
  state.img.aligned_he = {};
  state.update_image_source_control = jest.fn();
  api.validate_landscape_layers(state, { image_source: 'he' });
  await api.apply_landscape_layers(state, context, { image_source: 'he' });
  expect(state.img.image_source).toBe('he');
  expect(layers.image_source).toBe('he');
  expect(state.update_image_source_control).toHaveBeenCalled();
  expect(shims.toggle_visibility_image_layers).toHaveBeenCalledWith(
    layers,
    true,
    true
  );
});
