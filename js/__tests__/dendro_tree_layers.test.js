/* global require */
const fs = require('fs');
const path = require('path');

class TestLayer {
  constructor(props) {
    this.id = props.id;
    this.props = props;
  }
  clone(next) {
    return new this.constructor({ ...this.props, ...next });
  }
}
class PathLayer extends TestLayer {}
class PolygonLayer extends TestLayer {}
class TextLayer extends TestLayer {}

const source = fs
  .readFileSync(
    path.join(__dirname, '../deck-gl/matrix/dendro_tree_layers.js'),
    'utf8'
  )
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const api = new Function(
  'PathLayer',
  'PolygonLayer',
  'TextLayer',
  `${source}; return { DENDRO_TREE_LAYER_KEYS, ini_dendro_tree_layers,
    update_dendro_tree_layers, empty_dendro_tree_data,
    remove_dendro_tree_layers };`
)(PathLayer, PolygonLayer, TextLayer);

describe('temporary dendrogram deck layers', () => {
  test('uses PathLayer, PolygonLayer, and TextLayer in layers_mat', () => {
    const layers = {};
    api.ini_dendro_tree_layers(layers);
    expect(layers.dendro_tree_background_layer).toBeInstanceOf(PolygonLayer);
    expect(layers.row_dendro_tree_branches_layer).toBeInstanceOf(PathLayer);
    expect(layers.col_dendro_tree_branches_layer).toBeInstanceOf(PathLayer);
    expect(layers.dendro_tree_water_layer).toBeInstanceOf(PolygonLayer);
    expect(layers.dendro_tree_caption_layer).toBeInstanceOf(TextLayer);
    expect(layers.dendro_tree_caption_layer.props).toMatchObject({
      background: true,
      sizeUnits: 'pixels',
      pickable: false,
    });
  });

  test('fades via deck layer opacity and removes layers on teardown', () => {
    const layers = {};
    api.ini_dendro_tree_layers(layers);
    const data = api.empty_dendro_tree_data();
    data.background = [{ polygon: [], color: [255, 255, 255, 200] }];
    data.caption = [
      {
        position: [17, 12],
        text: 'Row tree',
        color: [24, 78, 137, 255],
        background_color: [255, 255, 255, 230],
      },
    ];
    api.update_dendro_tree_layers(layers, data, {
      opacity: 0,
      revision: 2,
      duration: 180,
    });
    expect(layers.dendro_tree_background_layer.props.opacity).toBe(0);
    expect(layers.dendro_tree_caption_layer.props.opacity).toBe(0);
    expect(
      layers.dendro_tree_background_layer.props.getFillColor(data.background[0])
    ).toEqual([255, 255, 255, 200]);
    expect(
      layers.dendro_tree_caption_layer.props.getBackgroundColor(data.caption[0])
    ).toEqual([255, 255, 255, 230]);
    expect(
      layers.dendro_tree_background_layer.props.transitions.opacity.duration
    ).toBe(180);
    expect(
      layers.dendro_tree_background_layer.props.transitions.getFillColor
    ).toBeUndefined();
    api.remove_dendro_tree_layers(layers);
    expect(Object.keys(layers)).toEqual([]);
  });
});
