/* global require */

const fs = require('fs');
const path = require('path');

const strip = (file) =>
  fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

class TileLayer {
  constructor(props) {
    this.props = props;
    this.id = props.id;
  }
  clone(props) {
    return new TileLayer({ ...this.props, ...props });
  }
}
const makeAPI = () => {
  const code = [
    strip('../global_variables/image_info.js'),
    strip('../deck-gl/layers/image_layers.js'),
    strip('../ui/image_source.js'),
    strip('../deck-gl/utils/layers_ist.js'),
    `return { make_image_layers, make_yearbook_image_layers,
      toggle_visibility_image_layers, toggle_visibility_single_image_layer,
      update_opacity_single_image_layer, make_image_source_control, set_image_info, get_layers_list };`,
  ].join('\n');
  return new Function(
    'TileLayer',
    'options',
    'getModelMatrixProps',
    'create_get_tile_data',
    'create_render_tile_sublayers',
    'create_simple_render_tile_sublayers',
    'refresh_layer',
    code
  )(
    TileLayer,
    {},
    () => ({}),
    (...args) => ({ type: 'files', args }),
    () => 'fluorescence',
    () => 'rgb',
    jest.fn()
  );
};
const state = (he = true) => ({
  img: {
    image_info: [{ name: 'dapi', button_name: 'DAPI', color: [0, 0, 255] }],
    image_format: '.jpeg',
    landscape_parameters: {
      max_pyramid_zoom: 12,
      tile_size: 250,
      ...(he
        ? {
            aligned_he: {
              name: 'h_and_e',
              button_name: 'H&E',
              image_format: '.webp',
            },
          }
        : {}),
    },
  },
  dimensions: { width: 3000, height: 2000, tileSize: 512 },
  global_base_url: '/data',
  obs_store: { viz_image_layers: { get: () => true } },
});
const control = (api, viz, layers) => {
  const container = document.createElement('div');
  const channels = document.createElement('div');
  container.appendChild(channels);
  return {
    channels,
    select: api.make_image_source_control(viz, layers, container, channels),
  };
};
const change = (select, value) => {
  select.value = value;
  select.dispatchEvent(new Event('change'));
};

test('legacy datasets retain fluorescence and have no visible source control', async () => {
  const api = makeAPI();
  const viz = state(false);
  const layers = { image_layers: await api.make_image_layers(viz) };
  expect(layers.image_layers).toHaveLength(1);
  expect(layers.image_layers[0].props.renderSubLayers).toBe('fluorescence');
  expect(control(api, viz, layers).select.hidden).toBe(true);
});

test('Landscape switches only backgrounds; RGB, format, IMG visibility and overlays survive', async () => {
  const api = makeAPI();
  const viz = state();
  const cells = {};
  const transcripts = {};
  const layers = {
    image_layers: await api.make_image_layers(viz),
    cell_layer: cells,
    trx_layer: transcripts,
  };
  const { select, channels } = control(api, viz, layers);
  expect(layers.image_layers.map((l) => l.props.visible)).toEqual([
    true,
    false,
  ]);
  change(select, 'he');
  expect(layers.image_layers.map((l) => l.props.visible)).toEqual([
    false,
    true,
  ]);
  expect(channels.style.display).toBe('none');
  const he = layers.image_layers[1];
  expect(he.props.renderSubLayers).toBe('rgb');
  expect(he.props.getTileData.args.slice(0, 4)).toEqual([
    '/data',
    'h_and_e',
    '.webp',
    12,
  ]);
  api.toggle_visibility_image_layers(layers, false);
  expect(layers.image_layers.every((l) => !l.props.visible)).toBe(true);
  api.toggle_visibility_image_layers(layers, true);
  expect(layers.image_layers.map((l) => l.props.visible)).toEqual([
    false,
    true,
  ]);
  change(select, 'primary');
  expect(channels.style.display).toBe('');
  expect(layers.image_layers.map((l) => l.props.visible)).toEqual([
    true,
    false,
  ]);
  expect(layers.cell_layer).toBe(cells);
  expect(layers.trx_layer).toBe(transcripts);
});

test('Yearbook keeps H&E selected on paging and preserves portrait IDs on opacity updates', async () => {
  const api = makeAPI();
  const viz = state();
  const portraits = [
    { x: 500, y: 500 },
    { x: 1500, y: 1000 },
  ];
  const layers = {
    image_layers: await api.make_yearbook_image_layers(
      viz,
      portraits,
      100,
      'page0'
    ),
  };
  const { select } = control(api, viz, layers);
  change(select, 'he');
  layers.image_layers = await api.make_yearbook_image_layers(
    viz,
    portraits,
    100,
    'page1'
  );
  api.toggle_visibility_image_layers(layers, true);
  expect(layers.image_layers.map((l) => l.props.visible)).toEqual([
    false,
    true,
    false,
    true,
  ]);
  expect(layers.image_layers[1].props.renderSubLayers).toBe('rgb');
  const ids = layers.image_layers.map((l) => l.id);
  api.update_opacity_single_image_layer(viz, layers, 'DAPI', 2, {
    DAPI: [0, 0, 255],
  });
  expect(layers.image_layers.map((l) => l.id)).toEqual(ids);
  change(select, 'primary');
  api.toggle_visibility_single_image_layer(layers, 'DAPI', false);
  expect(layers.image_layers.every((l) => !l.props.visible)).toBe(true);
});

test('RGB sources use the existing Parquet reader in both views', async () => {
  const api = makeAPI();
  const viz = state();
  viz.use_row_groups = true;
  const reader = { readTile: jest.fn(async () => null) };
  viz.row_group_readers = { images: { h_and_e: reader } };
  const landscape = await api.make_image_layers(viz);
  const yearbook = await api.make_yearbook_image_layers(
    viz,
    [{ x: 100, y: 100 }],
    100,
    'page0'
  );
  for (const layers of [landscape, yearbook]) {
    expect(layers[1].props.renderSubLayers).toBe('rgb');
    // eslint-disable-next-line no-await-in-loop
    await layers[1].props.getTileData({ index: { x: 2, y: 3, z: -1 } });
    expect(reader.readTile).toHaveBeenLastCalledWith(11, 2, 3);
  }
});

test('switching to a dataset without H&E resets the source and hides the control', async () => {
  const api = makeAPI();
  const viz = state();
  const layers = { image_layers: await api.make_image_layers(viz) };
  const { select, channels } = control(api, viz, layers);
  change(select, 'he');
  delete viz.img.landscape_parameters.aligned_he;
  api.set_image_info(viz.img, viz.img.image_info);
  layers.image_layers = await api.make_image_layers(viz);
  viz.update_image_source_control();
  expect(select.hidden).toBe(true);
  expect(channels.style.display).toBe('');
  expect(layers.image_source).toBe('primary');
  expect(layers.image_layers[0].props.visible).toBe(true);
});

test('inactive H&E tiles are not submitted to deck.gl for loading', async () => {
  const api = makeAPI();
  const viz = state();
  const layers = { image_layers: await api.make_image_layers(viz) };
  expect(api.get_layers_list(layers, true, viz)).toEqual([
    layers.image_layers[0],
  ]);
  layers.image_source = 'he';
  expect(api.get_layers_list(layers, true, viz)).toEqual([
    layers.image_layers[1],
  ]);
});

test('fluorescence channel selection survives switching backgrounds', async () => {
  const api = makeAPI();
  const viz = state();
  const layers = { image_layers: await api.make_image_layers(viz) };
  const { select } = control(api, viz, layers);
  api.toggle_visibility_single_image_layer(layers, 'DAPI', false);
  change(select, 'he');
  expect(layers.image_layers.map((l) => l.props.visible)).toEqual([
    false,
    true,
  ]);
  change(select, 'primary');
  expect(layers.image_layers.every((l) => !l.props.visible)).toBe(true);
});

test('legacy single histology images keep RGB rendering when opacity changes', async () => {
  const api = makeAPI();
  const viz = state(false);
  viz.img.image_info = [{ name: 'h_and_e', button_name: 'H&E' }];
  const layers = { image_layers: await api.make_image_layers(viz) };
  api.update_opacity_single_image_layer(viz, layers, 'H&E', 2, {});
  expect(layers.image_layers[0].props.renderSubLayers).toBe('rgb');
  expect(layers.image_layers[0].props.opacity).toBe(0.4);
});
