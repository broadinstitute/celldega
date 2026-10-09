/* global require */

const fs = require('fs');
const path = require('path');

const readSource = (file) =>
  fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const stripImports = (source) =>
  source
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export \{[^}]*\} from [^;]+;$/gm, '')
    .replace(/^export const /gm, 'const ');

// Keep the real initializer, slider event, size calculation and layer refresh
// together; stub only the fetched data and deck.gl layer object.
const controls = new Function(`
  class PointCloudLayer {
    constructor(props) { this.props = props; }
    clone(props) { return new PointCloudLayer({ ...this.props, ...props }); }
  }
  const options = { fetch: {} };
  const CELL_COLOR_SIZE = 4;
  const get_arrow_table = async () => ({});
  const get_scatter_data = () => ({ length: 2, attributes: {
    getPosition: { value: new Float32Array([0, 0, 0, 100, 100, 100]), size: 3 }
  }});
  const set_cell_names_array = (cats) => { cats.cell_names_array = ['a', 'b']; };
  const set_cell_name_to_index_map = () => {};
  const set_color_dict_gene = async () => {};
  const createEmptyCellCompact = () => ({});
  const getModelMatrixProps = () => ({});
  const getVizCellColorContext = (state) => ({
    cellNames: state.cats.cell_names_array, isClusterMode: true, selectedCats: []
  });
  const update_cell_color_buffer = () => new Uint8Array(8);
  ${stripImports(readSource('global_variables/image_info.js'))}
  ${stripImports(readSource('deck-gl/layers/cell_layer.js'))}
  ${stripImports(readSource('utils/refresh_layer.js'))}
  ${stripImports(readSource('ui/sliders.js'))}
  return { ini_cell_layer, ini_slider, get_point_cloud_cell_radius,
    update_cell_layer_radius, refresh_layer, is_orbit_technology };
`)();

const makeState = (cell_size) => ({
  spatial: { cell_size },
  img: { landscape_parameters: { technology: 'point-cloud' } },
  cats: {
    has_meta_cell: true,
    meta_cell_attr: ['cluster'],
    inst_cell_attr: 'cluster',
    meta_cell: { a: ['A'], b: ['A'] },
  },
  genes: {},
  seg: { version: 'default' },
  umap: { has_umap: false },
  combo_data: {},
  containers: { root_dim: { height: 600 } },
  root: { clientWidth: 800 },
  sliders: {},
  obs_store: {
    umap_state: { get: () => false },
    deck_check: { get: () => ({}), set: jest.fn() },
  },
});

describe('CellCloud cell diameter and slider', () => {
  test.each([
    [undefined, 5],
    [10, 5],
    [16, 8],
    [0, 0],
  ])(
    'initial diameter %s produces radius %s and does not jump at midpoint',
    async (diameter, radius) => {
      const state = makeState(diameter);
      const layers = {
        cell_layer: await controls.ini_cell_layer('/data', state),
      };
      expect(layers.cell_layer.props.pointSize).toBe(radius);
      expect(layers.cell_layer.props.sizeUnits).toBe('meters');

      controls.ini_slider('cell', {}, layers, state);
      expect(state.sliders.cell.value).toBe('50');
      state.sliders.cell.dispatchEvent(new Event('input'));
      expect(layers.cell_layer.props.pointSize).toBe(radius);
      expect(state.obs_store.deck_check.set).toHaveBeenCalledTimes(2);
    }
  );

  test('slider scales the configured diameter, including zero and double size', async () => {
    const state = makeState(16);
    const layers = {
      cell_layer: await controls.ini_cell_layer('/data', state),
    };
    controls.ini_slider('cell', {}, layers, state);

    for (const [value, radius] of [
      [25, 4],
      [75, 12],
      [100, 16],
      [0, 0],
    ]) {
      state.sliders.cell.value = value;
      state.sliders.cell.dispatchEvent(new Event('input'));
      expect(layers.cell_layer.props.pointSize).toBe(radius);
    }
  });

  test('Python size changes preserve the multiplier and unregister on disposal', async () => {
    const state = makeState(16);
    const layers = {
      cell_layer: await controls.ini_cell_layer('/data', state),
    };
    controls.ini_slider('cell', {}, layers, state);
    state.sliders.cell.value = 75;

    const listeners = new Map();
    state.model = {
      get: () => 8,
      on: (event, callback) => listeners.set(event, callback),
      off: (event) => listeners.delete(event),
    };
    const cleanup = [];
    const source = readSource('viz/landscape_ist.js');
    const start = source.indexOf('  if (viz_state.model?.on) {');
    const end = source.indexOf('  const ui_container =', start);
    new Function(
      'viz_state',
      'layers_obj',
      'deck_ist',
      'cleanup_callbacks',
      'get_point_cloud_cell_radius',
      'update_cell_layer_radius',
      'refresh_layer',
      source.slice(start, end)
    )(
      state,
      layers,
      {},
      cleanup,
      controls.get_point_cloud_cell_radius,
      controls.update_cell_layer_radius,
      controls.refresh_layer
    );

    listeners.get('change:cell_size')();
    expect(state.spatial.cell_size).toBe(8);
    expect(state.sliders.cell.value).toBe('75');
    expect(layers.cell_layer.props.pointSize).toBe(6);
    cleanup.forEach((dispose) => dispose());
    expect(listeners.size).toBe(0);
  });

  test('2D cell slider still controls an absolute radius', () => {
    const state = makeState(16);
    state.img.landscape_parameters.technology = 'Xenium';
    const layers = {
      cell_layer: {
        props: { getRadius: 5 },
        clone(props) {
          return { ...this, props: { ...this.props, ...props } };
        },
      },
    };
    controls.ini_slider('cell', {}, layers, state);
    expect(state.sliders.cell.value).toBe('25');
    state.sliders.cell.value = 50;
    state.sliders.cell.dispatchEvent(new Event('input'));
    expect(layers.cell_layer.props.getRadius).toBe(10);
  });

  test.each([undefined, 0, 16])(
    'widget renderer forwards cell_size=%s',
    async (size) => {
      const source = readSource('celldega.js');
      const start = source.indexOf('const render_landscape_ist =');
      const end = source.indexOf('const render_landscape_h_e =', start);
      const landscape = jest.fn();
      const render = new Function(
        'landscape_ist',
        'is_orbit_technology',
        `${source.slice(start, end)}; return render_landscape_ist;`
      )(landscape, controls.is_orbit_technology);
      await render({
        el: document.createElement('div'),
        model: { get: (name) => (name === 'cell_size' ? size : undefined) },
      });
      expect(landscape.mock.calls[0].at(-1)).toBe(size ?? 10);
    }
  );
});
