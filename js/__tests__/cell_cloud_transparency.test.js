/* global require */

const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export \{[^}]*\} from [^;]+;$/gm, '')
    .replace(/^export const /gm, 'const ');

// Emulate the depth and alpha operations at a pixel covered by two cells.
// The real CellCloud subclass decides GPU parameters; deck.gl's other work
// and shader compilation are outside the behavior this regression exercises.
class PointCloudLayer {
  constructor(props) {
    this.props = props;
    this.context = {
      device: {
        parameters: { depthTest: true, depthMask: true },
        withParametersWebGL(parameters, draw) {
          const previous = this.parameters;
          this.parameters = { ...previous, ...parameters };
          try {
            draw();
          } finally {
            this.parameters = previous;
          }
        },
      },
    };
  }
  clone(props) {
    return new this.constructor({ ...this.props, ...props });
  }
  draw() {
    this.drawParameters = { ...this.context.device.parameters };
    let depth = Infinity;
    let alpha = 0;
    let picked = -1;
    for (const cell of this.props.pixels || []) {
      const { depth: cellDepth, alpha: cellAlpha, source } = cell;
      if (!this.drawParameters.depthTest || cellDepth < depth) {
        alpha = cellAlpha + alpha * (1 - cellAlpha);
        picked = source;
        if (this.drawParameters.depthMask) depth = cellDepth;
      }
    }
    this.result = { alpha, picked };
  }
}

const { CellCloudLayer, refresh_cell_layer_data } = new Function(
  'PointCloudLayer',
  `
    ${read('deck-gl/layers/CellCloudLayer.js')}
    ${read('global_variables/image_info.js')}
    ${read('deck-gl/layers/cell_color.js')}
    ${read('deck-gl/layers/cell_layer.js')}
    return {CellCloudLayer, refresh_cell_layer_data};
  `
)(PointCloudLayer);

const near = { depth: 1, alpha: 0.2, source: 'near-original-cell' };
const far = { depth: 2, alpha: 0.6, source: 'far-original-cell' };

const render = (pixels, transparent = true, picking = false) => {
  const layer = new CellCloudLayer({
    pixels,
    cellCloudTransparent: transparent,
  });
  layer.draw({
    parameters: { blend: !picking, depthTest: true },
    moduleParameters: { picking: { isActive: picking } },
  });
  return layer;
};

describe('CellCloud gene transparency', () => {
  test('blends the same expression alpha from the front and back', () => {
    expect(render([near, far]).result.alpha).toBeCloseTo(0.68);
    expect(render([far, near]).result.alpha).toBeCloseTo(0.68);
    expect(render([near, far]).drawParameters).toEqual({
      depthTest: false,
      depthMask: false,
    });
    expect(render([near, far]).context.device.parameters).toEqual({
      depthTest: true,
      depthMask: true,
    });
  });

  test('restores WebGL state even if the point draw fails', () => {
    const layer = new CellCloudLayer({
      cellCloudTransparent: true,
      pixels: [
        {
          get depth() {
            throw new Error('draw failed');
          },
        },
      ],
    });
    expect(() => layer.draw({})).toThrow('draw failed');
    expect(layer.context.device.parameters).toEqual({
      depthTest: true,
      depthMask: true,
    });
  });

  test('picking retains the nearest original cell in either draw order', () => {
    for (const order of [
      [near, far],
      [far, near],
    ]) {
      const layer = render(order, true, true);
      expect(layer.result.picked).toBe('near-original-cell');
      expect(layer.drawParameters.depthMask).toBe(true);
      expect(layer.drawParameters.depthTest).toBe(true);
    }
  });

  test('opaque cluster coloring keeps depth writes', () => {
    expect(render([near, far], false).result.alpha).toBeCloseTo(0.2);
    expect(render([near, far], false).drawParameters.depthMask).toBe(true);
  });

  test('switching expression, cluster, and highlighted modes updates the live layer', () => {
    const state = {
      img: { landscape_parameters: { technology: 'point-cloud' } },
      spatial: {
        cell_point_count: 3,
        cell_positions: Float32Array.from([1, 2, 3, 4, 5, 6, 7, 8, 9]),
      },
      cats: {
        cat: 'GeneA',
        selected_cats: ['GeneA'],
        cell_names_array: ['cell-A', 'cell-B', 'cell-C'],
        cell_cats: ['A', 'B', 'A'],
        color_dict_cluster: { A: [10, 20, 30], B: [40, 50, 60] },
        cell_exp_array: Uint8Array.from([0, 100, 200]),
      },
      highlighted_cells: new Set(),
      obs_store: { umap_state: { get: () => false } },
    };
    const layers = { cell_layer: new CellCloudLayer({}) };
    refresh_cell_layer_data(layers, state);
    expect(layers.cell_layer.props.cellCloudTransparent).toBe(true);
    expect(Array.from(state.spatial.visible_cell_indices)).toEqual([1, 2]);
    // Filtering and picking retain canonical IDs; no camera sort or data reorder.
    expect(
      Array.from(layers.cell_layer.props.data.attributes.getPosition.value)
    ).toEqual([4, 5, 6, 7, 8, 9]);
    expect(
      Array.from(layers.cell_layer.props.data.attributes.getColor.value)
    ).toEqual([255, 0, 0, 100, 255, 0, 0, 200]);
    state.cats.cat = 'cluster';
    state.cats.selected_cats = [];
    refresh_cell_layer_data(layers, state);
    expect(layers.cell_layer.props.cellCloudTransparent).toBe(false);
    expect(state.spatial.visible_cell_indices).toBeNull();
    state.cats.cat = 'GeneA';
    state.highlighted_cells.add('cell-B');
    refresh_cell_layer_data(layers, state);
    expect(layers.cell_layer.props.cellCloudTransparent).toBe(false);
    expect(Array.from(state.spatial.visible_cell_indices)).toEqual([1]);
    expect(
      Array.from(layers.cell_layer.props.data.attributes.getColor.value)
    ).toEqual([0, 0, 255, 255]);
  });
});
