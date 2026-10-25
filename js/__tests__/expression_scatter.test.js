/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const gates = new Function(`${read('umap/embedding_gates.js')}
  return { fingerprint, point_in_gate, gate_cell_ids, space_key,
    sync_embedding_gates, show_space_gates };`)();
const load = jest.fn();
const scatter = new Function(
  'ViewMode',
  'get_scatterplot_cell_data',
  'calc_and_update_rgn_bar_graph',
  'load_gene_expression',
  'fingerprint',
  'show_space_gates',
  `${read('umap/expression_scatter.js')}
  return { expression_axis, interpolate_positions, initialize_expression_scatter };`
)(
  class {},
  (state) => ({
    attributes: {
      getPosition: {
        value:
          state.spatial.embedding_animation_positions ||
          state.spatial.cell_umap_scatter_positions,
      },
    },
  }),
  jest.fn(),
  load,
  gates.fingerprint,
  gates.show_space_gates
);

const observable = (value) => {
  const callbacks = new Set();
  return {
    get: () => value,
    set: (next) => {
      value = next;
      callbacks.forEach((cb) => cb(next));
    },
    subscribe: (cb) => {
      callbacks.add(cb);
      return () => callbacks.delete(cb);
    },
  };
};
class Layer {
  constructor(props) {
    this.props = props;
  }
  clone(props) {
    return new Layer({ ...this.props, ...props });
  }
}
const setup = ({ spatialOnly = false } = {}) => {
  const callbacks = {};
  const values = {
    xy_genes: [],
    xy_scale: 'log1p',
    xy_auto_switch: true,
    gates: { type: 'FeatureCollection', features: [] },
  };
  const model = {
    get: (key) => values[key],
    set: (key, value) => {
      values[key] = value;
      callbacks[`change:${key}`]?.();
    },
    on: (event, cb) => {
      callbacks[event] = cb;
    },
    off: (event) => {
      delete callbacks[event];
    },
    save_changes: jest.fn(),
  };
  const umap = new Float32Array([0, 0, 100, 100, 50, 50]);
  const state = {
    model,
    spatial: {
      cell_umap_scatter_positions: spatialOnly ? undefined : umap,
      cell_scatter_data: {
        length: 3,
        attributes: { getPosition: { value: umap, size: 2 } },
      },
    },
    genes: { gene_names: spatialOnly ? [] : ['A', 'B'] },
    global_base_url: 'data',
    seg: { version: 'default' },
    cats: {
      cell_names_array: ['a', 'b', 'c'],
      cell_name_to_index_map: new Map([
        ['a', 0],
        ['b', 1],
        ['c', 2],
      ]),
      cat: 'cluster',
      cell_cats: ['T', 'B', 'T'],
      selected_cats: [],
    },
    edit: { feature_collection: { type: 'FeatureCollection', features: [] } },
    obs_store: {
      landscape_view: observable(spatialOnly ? 'spatial' : 'umap'),
      viz_edit_layer: observable(false),
      selected_cells: observable([]),
      selected_cats: observable([]),
      selected_genes: observable([]),
    },
    containers: {
      view_modes: document.createElement('div'),
      image: document.createElement('div'),
    },
  };
  const layers = {
    cell_layer: new Layer({
      data: { attributes: { getPosition: { value: umap } } },
    }),
  };
  const dispose = scatter.initialize_expression_scatter(
    state,
    layers,
    jest.fn(),
    {}
  );
  return { state, layers, model, dispose };
};

describe('expression scatter and coordinate-aware gates', () => {
  beforeEach(() => {
    load.mockReset();
    load.mockResolvedValue({ cell_names: ['a', 'b'], cell_exp: [0, 9] });
  });

  test('linear/log1p axes retain zeros and constant axes overlap at the center', () => {
    expect(
      Array.from(
        scatter.expression_axis(new Float64Array([0, 1, 9]), 'linear').positions
      )
    ).toEqual([0, 10000 / 9, 10000]);
    const log = scatter.expression_axis(
      new Float64Array([0, 1, 9]),
      'log1p',
      0,
      10000,
      true
    ).positions;
    expect(log[0]).toBe(10000);
    expect(log[1]).toBeCloseTo(6989.7, 0);
    expect(log[2]).toBe(0);
    expect(
      Array.from(
        scatter.expression_axis(new Float64Array(3), 'log1p').positions
      )
    ).toEqual([5000, 5000, 5000]);
  });

  test('animation interpolation preserves cell ordering and endpoints', () => {
    const from = [0, 10, 20, 30],
      to = [10, 0, 40, 10],
      out = new Float32Array(4);
    expect(
      Array.from(scatter.interpolate_positions(from, to, 0.5, out))
    ).toEqual([5, 5, 30, 20]);
    expect(Array.from(scatter.interpolate_positions(from, to, 1, out))).toEqual(
      to
    );
  });

  test('two selected genes enter XY, preserve sparse zeros, and can return to UMAP', async () => {
    const { state, model, dispose } = setup();
    state.obs_store.selected_genes.set(['A', 'B']);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(state.obs_store.landscape_view.get()).toBe('xy');
    expect(model.get('xy_genes')).toEqual(['A', 'B']);
    const buttons = state.containers.view_modes.querySelectorAll('button');
    expect(buttons[0].style.display).toBe('none');
    expect(buttons[1].textContent).toBe('LIN');
    expect(buttons[2].textContent).toBe('LOG');
    expect(state.embedding_space).toMatchObject({
      kind: 'xy',
      genes: ['A', 'B'],
      scale: 'log1p',
    });
    expect(Array.from(state.spatial.cell_xy_scatter_positions)).toEqual([
      0, 100, 100, 0, 0, 100,
    ]);
    model.set('xy_scale', 'linear');
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(state.embedding_space.scale).toBe('linear');
    model.set('landscape_state', 'umap');
    expect(state.obs_store.landscape_view.get()).toBe('umap');
    expect(state.embedding_space.kind).toBe('umap');
    dispose();
  });

  test('cluster and explicit multi-cell selections are published to Python', () => {
    const { state, model, dispose } = setup();
    state.cats.selected_cats = ['T'];
    state.obs_store.selected_cats.set(['T']);
    expect(model.get('selected_cells')).toEqual(['a', 'c']);
    state.obs_store.selected_cells.set(['a', 'b']);
    expect(model.get('selected_cells')).toEqual(['a', 'b']);
    state.obs_store.selected_cells.set([]);
    expect(model.get('selected_cells')).toEqual([]);
    dispose();
  });

  test('typed axes and LIN/LOG update expression; animation uploads distinct buffers', async () => {
    const frames = [];
    const raf = jest
      .spyOn(window, 'requestAnimationFrame')
      .mockImplementation((cb) => {
        frames.push(cb);
        return frames.length;
      });
    const now = jest.spyOn(performance, 'now').mockReturnValue(0);
    const { state, layers, model, dispose } = setup();
    state.obs_store.landscape_view.set('xy');
    const inputs = state.containers.image.querySelectorAll('input');
    inputs[0].value = 'A';
    inputs[0].dispatchEvent(new Event('input'));
    inputs[1].value = 'B';
    inputs[1].dispatchEvent(new Event('input'));
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(model.get('xy_genes')).toEqual(['A', 'B']);
    frames.pop()(200);
    const first = layers.cell_layer.props.data.attributes.getPosition.value;
    frames.pop()(400);
    const second = layers.cell_layer.props.data.attributes.getPosition.value;
    expect(first).not.toBe(second);
    expect(Array.from(first)).not.toEqual(Array.from(second));
    state.containers.view_modes.querySelectorAll('button')[1].click();
    expect(model.get('xy_scale')).toBe('linear');
    dispose();
    raf.mockRestore();
    now.mockRestore();
  });

  test('integer DegaFiles indices map to the same cell order, including implicit zeros', async () => {
    load.mockResolvedValue({ cell_names: [0n, 2n], cell_exp: [2, 8] });
    const { state, dispose } = setup();
    state.vector_name_integer = true;
    state.obs_store.selected_genes.set(['A', 'B']);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(Array.from(state.spatial.cell_xy_scatter_positions)).toEqual([
      Math.fround((Math.log1p(2) / Math.log1p(8)) * 100),
      Math.fround((1 - Math.log1p(2) / Math.log1p(8)) * 100),
      0,
      100,
      100,
      0,
    ]);
    dispose();
  });

  test('a pending gene request cannot move cells after returning to UMAP', async () => {
    const complete = [];
    load.mockImplementation(
      () => new Promise((resolve) => complete.push(resolve))
    );
    const { state, dispose } = setup();
    state.obs_store.selected_genes.set(['A', 'B']);
    state.obs_store.landscape_view.set('umap');
    complete.forEach((resolve) =>
      resolve({ cell_names: ['a'], cell_exp: [9] })
    );
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(state.embedding_space.kind).toBe('umap');
    expect(state.spatial.cell_xy_scatter_positions).toBeUndefined();
    dispose();
  });

  test('gates include holes and multipolygons', () => {
    const square = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
      [0, 0],
    ];
    const hole = [
      [4, 4],
      [6, 4],
      [6, 6],
      [4, 6],
      [4, 4],
    ];
    const geometry = { type: 'Polygon', coordinates: [square, hole] };
    expect(
      gates.gate_cell_ids(geometry, [1, 1, 5, 5, 11, 11], ['in', 'hole', 'out'])
    ).toEqual(['in']);
    expect(
      gates.point_in_gate([1, 1], {
        type: 'MultiPolygon',
        coordinates: [[square]],
      })
    ).toBe(true);
  });

  test('physical NBHDs sync vertices and membership without requiring UMAP or genes', () => {
    const { state, layers, model, dispose } = setup({ spatialOnly: true });
    expect(state.neighborhood_space.kind).toBe('spatial');
    expect(state.containers.view_modes.querySelectorAll('button')).toHaveLength(
      0
    );
    const space = state.neighborhood_space;
    state.edit.feature_collection.features = [
      {
        type: 'Feature',
        properties: { name: 'physical' },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-1, -1],
              [60, -1],
              [60, 60],
              [-1, 60],
              [-1, -1],
            ],
          ],
        },
      },
    ];
    // false continues the existing nbhd_geojson -> inverse tissue-affine path.
    expect(gates.sync_embedding_gates(state)).toBe(false);
    expect(model.get('gates').features[0].properties).toMatchObject({
      cell_ids: ['a', 'c'],
      coordinate_space: space,
      x: [[-1, 60, 60, -1, -1]],
      y: [[-1, -1, 60, 60, -1]],
    });
    gates.show_space_gates(state, layers, {
      kind: 'umap',
      dataset: space.dataset,
    });
    expect(state.edit.feature_collection.features).toHaveLength(0);
    gates.show_space_gates(state, layers, space);
    expect(state.edit.feature_collection.features[0].properties.name).toBe(
      'physical'
    );
    state.edit.feature_collection.features = [];
    gates.sync_embedding_gates(state);
    gates.show_space_gates(state, layers, space);
    expect(state.edit.feature_collection.features).toHaveLength(0);
    dispose();
  });

  test('saving/editing gates preserves other spaces and restores only matching polygons', () => {
    const { state, layers, model, dispose } = setup();
    const space = state.embedding_space;
    state.edit.feature_collection.features = [
      {
        type: 'Feature',
        properties: { name: 'T cells' },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-1, -1],
              [60, -1],
              [60, 60],
              [-1, 60],
              [-1, -1],
            ],
          ],
        },
      },
    ];
    expect(gates.sync_embedding_gates(state)).toBe(true);
    expect(model.get('gates').features[0].properties).toMatchObject({
      cell_ids: ['a', 'c'],
      cell_count: 2,
      coordinate_space: space,
    });
    const xy = { kind: 'xy', genes: ['A', 'B'], scale: 'linear' };
    gates.show_space_gates(state, layers, xy);
    expect(state.edit.feature_collection.features).toHaveLength(0);
    gates.sync_embedding_gates(state);
    expect(model.get('gates').features).toHaveLength(1);
    gates.show_space_gates(state, layers, space);
    expect(state.edit.feature_collection.features[0].properties.name).toBe(
      'T cells'
    );
    dispose();
  });
});
