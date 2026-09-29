import { PathLayer, PolygonLayer, TextLayer } from 'deck.gl';

export const DENDRO_TREE_LAYER_KEYS = [
  'dendro_tree_background_layer',
  'row_dendro_tree_branches_layer',
  'col_dendro_tree_branches_layer',
  'dendro_tree_water_layer',
  'dendro_tree_cut_outline_layer',
  'dendro_tree_cut_layer',
  'dendro_tree_caption_layer',
];

const fade_color = (color, opacity) => [
  color[0],
  color[1],
  color[2],
  Math.round((color[3] ?? 255) * opacity),
];

const ease_out = (t) => 1 - (1 - t) ** 3;

const color_transition = (duration) =>
  duration > 0 ? { duration, easing: ease_out } : false;

const polygon_layer = (id) =>
  new PolygonLayer({
    id,
    data: [],
    getPolygon: (d) => d.polygon,
    getFillColor: (d) => d.color,
    stroked: false,
    pickable: false,
    antialiasing: false,
    parameters: { depthTest: false },
  });

const path_layer = (id) =>
  new PathLayer({
    id,
    data: [],
    getPath: (d) => d.path,
    getColor: (d) => d.color,
    getWidth: (d) => d.width,
    widthUnits: 'pixels',
    widthMinPixels: 0,
    pickable: false,
    parameters: { depthTest: false },
  });

const caption_layer = () =>
  new TextLayer({
    id: 'dendro-tree-caption-layer',
    data: [],
    getPosition: (d) => d.position,
    getText: (d) => d.text,
    getColor: (d) => d.color,
    getSize: 12,
    getTextAnchor: 'start',
    getAlignmentBaseline: 'top',
    fontFamily: 'system-ui, sans-serif',
    sizeUnits: 'pixels',
    sizeScale: 1,
    background: true,
    getBackgroundColor: (d) => d.background_color,
    getBorderWidth: 0,
    backgroundPadding: [7, 4],
    pickable: false,
    parameters: { depthTest: false },
  });

/** Add the temporary-tree layers to the matrix layer registry. */
export const ini_dendro_tree_layers = (layers_mat) => {
  layers_mat.dendro_tree_background_layer = polygon_layer(
    'dendro-tree-background-layer'
  );
  layers_mat.row_dendro_tree_branches_layer = path_layer(
    'row-dendro-tree-branches-layer'
  );
  layers_mat.col_dendro_tree_branches_layer = path_layer(
    'col-dendro-tree-branches-layer'
  );
  layers_mat.dendro_tree_water_layer = polygon_layer('dendro-tree-water-layer');
  layers_mat.dendro_tree_cut_outline_layer = path_layer(
    'dendro-tree-cut-outline-layer'
  );
  layers_mat.dendro_tree_cut_layer = path_layer('dendro-tree-cut-layer');
  layers_mat.dendro_tree_caption_layer = caption_layer();
};

const clone_polygon = (layer, data, opacity, revision, duration) =>
  layer.clone({
    data,
    getFillColor: (d) => fade_color(d.color, opacity),
    updateTriggers: { getFillColor: revision },
    transitions: { getFillColor: color_transition(duration) },
  });

const clone_path = (layer, data, opacity, revision, duration) =>
  layer.clone({
    data,
    getColor: (d) => fade_color(d.color, opacity),
    updateTriggers: { getColor: revision },
    transitions: { getColor: color_transition(duration) },
  });

const clone_caption = (layer, data, opacity, revision, duration) =>
  layer.clone({
    data,
    getColor: (d) => fade_color(d.color, opacity),
    getBackgroundColor: (d) => fade_color(d.background_color, opacity),
    updateTriggers: {
      getColor: revision,
      getBackgroundColor: revision,
    },
    transitions: {
      getColor: color_transition(duration),
      getBackgroundColor: color_transition(duration),
    },
  });

/**
 * Replace preview geometry and/or animate its opacity using deck.gl attribute
 * transitions. The data is intentionally retained during a fade so deck.gl can
 * interpolate it without an external animation loop.
 */
export const update_dendro_tree_layers = (
  layers_mat,
  data,
  { opacity = 1, revision = 0, duration = 0 } = {}
) => {
  layers_mat.dendro_tree_background_layer = clone_polygon(
    layers_mat.dendro_tree_background_layer,
    data.background,
    opacity,
    revision,
    duration
  );
  layers_mat.row_dendro_tree_branches_layer = clone_path(
    layers_mat.row_dendro_tree_branches_layer,
    data.row_branches,
    opacity,
    revision,
    duration
  );
  layers_mat.col_dendro_tree_branches_layer = clone_path(
    layers_mat.col_dendro_tree_branches_layer,
    data.col_branches,
    opacity,
    revision,
    duration
  );
  layers_mat.dendro_tree_water_layer = clone_polygon(
    layers_mat.dendro_tree_water_layer,
    data.water,
    opacity,
    revision,
    duration
  );
  layers_mat.dendro_tree_cut_outline_layer = clone_path(
    layers_mat.dendro_tree_cut_outline_layer,
    data.cut_outline,
    opacity,
    revision,
    duration
  );
  layers_mat.dendro_tree_cut_layer = clone_path(
    layers_mat.dendro_tree_cut_layer,
    data.cut,
    opacity,
    revision,
    duration
  );
  layers_mat.dendro_tree_caption_layer = clone_caption(
    layers_mat.dendro_tree_caption_layer,
    data.caption,
    opacity,
    revision,
    duration
  );
};

export const empty_dendro_tree_data = () => ({
  background: [],
  row_branches: [],
  col_branches: [],
  water: [],
  cut_outline: [],
  cut: [],
  caption: [],
});

/** Remove the temporary layers from the matrix registry on finalization. */
export const remove_dendro_tree_layers = (layers_mat) => {
  DENDRO_TREE_LAYER_KEYS.forEach((key) => delete layers_mat[key]);
};
