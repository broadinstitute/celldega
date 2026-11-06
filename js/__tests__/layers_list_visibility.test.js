/* global require */

const fs = require('fs');
const path = require('path');

const strip = (file) =>
  fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const { get_layers_list } = new Function(
  [
    strip('../global_variables/image_info.js'),
    strip('../deck-gl/utils/layers_ist.js'),
    'return { get_layers_list };',
  ].join('\n')
)();

class Layer {
  constructor(props) {
    this.props = { visible: true, ...props };
    this.id = props.id;
    this.internalState = null;
  }
  clone(props) {
    return new Layer({ ...this.props, ...props });
  }
}

// Mirrors deck.gl's LayerManager matching: layers absent from the next list
// are finalized, and a finalized instance cannot be initialized again.
const makeDeck = () => {
  let current = new Map();
  return {
    setLayers(layers) {
      const next = new Map();
      for (const layer of layers) {
        const old = current.get(layer.id);
        if (old) {
          layer.internalState = old.internalState;
        } else {
          if (layer.internalState)
            throw new Error('deck.gl: assertion failed.');
          layer.internalState = { id: layer.id };
        }
        next.set(layer.id, layer);
      }
      current = next;
    },
  };
};

const makeLayers = () => ({
  background_layer: new Layer({ id: 'background' }),
  image_layers: [new Layer({ id: 'dapi' })],
  path_layer: new Layer({ id: 'path-layer-data-26' }),
  cell_layer: new Layer({ id: 'cell' }),
  trx_layer: new Layer({ id: 'trx' }),
});

describe('get_layers_list close-up layers', () => {
  test('zooming out hides path and transcript layers without dropping them', () => {
    const layers = makeLayers();
    const ids = (list) => list.map((layer) => layer.id);

    const closeUp = get_layers_list(layers, true, {});
    const zoomedOut = get_layers_list(layers, false, {});

    expect(closeUp).toContain(layers.path_layer);
    expect(closeUp).toContain(layers.trx_layer);
    expect(ids(zoomedOut)).toEqual(ids(closeUp));
    const hidden = zoomedOut.filter((layer) =>
      [layers.path_layer.id, layers.trx_layer.id].includes(layer.id)
    );
    expect(hidden.map((layer) => layer.props.visible)).toEqual([false, false]);
    expect(layers.path_layer.props.visible).toBe(true);
  });

  test('zooming back in reuses live layers instead of finalized ones', () => {
    const layers = makeLayers();
    const deck = makeDeck();

    deck.setLayers(get_layers_list(layers, true, {}));
    deck.setLayers(get_layers_list(layers, false, {}));
    // Zoom-in can render before new tiles replace the path layer.
    expect(() =>
      deck.setLayers(get_layers_list(layers, true, {}))
    ).not.toThrow();
  });

  test('point clouds omit path and transcript layers', () => {
    const layers = makeLayers();
    const viz = {
      img: { landscape_parameters: { technology: 'point-cloud' } },
    };
    for (const closeUp of [true, false]) {
      const ids = get_layers_list(layers, closeUp, viz).map(
        (layer) => layer.id
      );
      expect(ids).toEqual(['background', 'dapi', 'cell']);
    }
  });
});
