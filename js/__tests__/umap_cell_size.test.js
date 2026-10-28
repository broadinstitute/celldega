/* global require */

const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export \{[^}]*\} from [^;]+;$/gm, '')
    .replace(/^export const /gm, 'const ');

const api = new Function(`
  ${read('global_variables/image_info.js')}
  ${read('deck-gl/layers/cell_color.js')}
  ${read('deck-gl/layers/cell_layer.js')}
  return { get_scatterplot_cell_data, refresh_cell_layer_data,
    update_cell_layer_radius, toggle_spatial_umap };
`)();

class Layer {
  constructor(props = {}) {
    this.props = props;
  }
  clone(props) {
    return new Layer({ ...this.props, ...props });
  }
}

const makeState = () => ({
  img: { landscape_parameters: { technology: 'Chromium' } },
  spatial: {
    cell_scatter_data: {
      length: 3,
      attributes: { getPosition: { value: new Float32Array(6), size: 2 } },
    },
  },
  umap: { has_umap: false },
  cats: {
    cat: 'cluster',
    cell_names_array: ['a', 'b', 'c'],
    cell_cats: ['A', 'B', 'A'],
    selected_cats: [],
    color_dict_cluster: { A: [10, 20, 30], B: [40, 50, 60] },
    cell_exp_array: [0, 128, 255],
  },
  highlighted_cells: new Set(),
  selection_token: 0,
  obs_store: { umap_state: { get: () => true } },
});

const radii = (data) => Array.from(data.attributes.getRadius.value);

describe('selected cells in UMAP views', () => {
  test('a cluster selection enlarges every selected cell and dims the rest', () => {
    const state = makeState();
    state.cats.selected_cats = ['A'];
    const data = api.get_scatterplot_cell_data(state);
    expect(radii(data)).toEqual([2.5, 1, 2.5]);
    expect(Array.from(data.attributes.getFillColor.value.slice(4, 8))).toEqual([
      128, 128, 128, 16,
    ]);
  });

  test('a multi-cell dendrogram selection enlarges all its cells and clearing resets sizes', () => {
    const state = makeState();
    const layers = { cell_layer: new Layer() };
    state.highlighted_cells = new Set(['a', 'b']);
    api.refresh_cell_layer_data(layers, state);
    expect(radii(layers.cell_layer.props.data)).toEqual([2.5, 2.5, 1]);
    expect(layers.cell_layer.props.radiusUnits).toBe('pixels');
    state.highlighted_cells.clear();
    api.refresh_cell_layer_data(layers, state);
    expect(radii(layers.cell_layer.props.data)).toEqual([1, 1, 1]);
  });

  test('gene selection enlarges cells expressing the selected gene', () => {
    const state = makeState();
    state.cats.cat = 'GeneA';
    state.cats.selected_cats = ['GeneA'];
    expect(radii(api.get_scatterplot_cell_data(state))).toEqual([1, 2.5, 2.5]);
  });

  test('XY and animated positions leave the original UMAP buffer intact', () => {
    const state = makeState();
    let view = 'xy';
    state.obs_store.landscape_view = { get: () => view };
    const umap = new Float32Array([0, 0, 1, 1, 2, 2]);
    const xy = new Float32Array([0, 2, 1, 0, 0, 0]);
    state.spatial.cell_umap_scatter_positions = umap;
    state.spatial.cell_xy_scatter_positions = xy;
    expect(
      api.get_scatterplot_cell_data(state).attributes.getPosition.value
    ).toBe(xy);
    const intermediate = new Float32Array([0, 1, 1, 0.5, 1, 1]);
    state.spatial.embedding_animation_positions = intermediate;
    expect(
      api.get_scatterplot_cell_data(state).attributes.getPosition.value
    ).toBe(intermediate);
    state.spatial.embedding_animation_positions = null;
    view = 'umap';
    expect(
      api.get_scatterplot_cell_data(state).attributes.getPosition.value
    ).toBe(umap);
    expect(Array.from(umap)).toEqual([0, 0, 1, 1, 2, 2]);
  });

  test('the cell slider scales selected points and can still hide every point', () => {
    const state = makeState();
    state.cats.selected_cats = ['A'];
    const layers = { cell_layer: new Layer() };
    api.update_cell_layer_radius(layers, 10, state);
    expect(radii(layers.cell_layer.props.data)).toEqual([5, 2, 5]);
    api.update_cell_layer_radius(layers, 0, state);
    expect(radii(layers.cell_layer.props.data)).toEqual([0, 0, 0]);
    expect(layers.cell_layer.props.radiusMinPixels).toBe(0);
  });

  test('returning to the spatial view restores equal radii in data units', () => {
    const state = makeState();
    state.cats.selected_cats = ['A'];
    state.obs_store.umap_state.get = () => false;
    const layers = { cell_layer: new Layer() };
    api.toggle_spatial_umap(null, layers, state);
    expect(radii(layers.cell_layer.props.data)).toEqual([5, 5, 5]);
    expect(layers.cell_layer.props.radiusUnits).toBe('common');
    expect(layers.cell_layer.props.radiusMinPixels).toBe(1);
  });

  test('embedding gates and cells share unrotated axes; physical view restores tissue rotation', () => {
    const state = makeState();
    const matrix = [0, 1, -1, 0];
    state.rotation = { modelMatrix: matrix };
    const layers = { cell_layer: new Layer() };
    api.toggle_spatial_umap(null, layers, state);
    expect(layers.cell_layer.props.modelMatrix).toBeNull();
    state.obs_store.umap_state.get = () => false;
    api.toggle_spatial_umap(null, layers, state);
    expect(layers.cell_layer.props.modelMatrix).toBe(matrix);
  });
});
