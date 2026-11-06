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

const ease_out = (t) => 1 - (1 - t) ** 3;

const opacity_transition = (duration) =>
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

const clone_layer = (layer, data, opacity, duration) =>
  layer.clone({
    data,
    opacity,
    transitions: { opacity: opacity_transition(duration) },
  });

/**
 * Replace preview geometry and/or animate its layer opacity. Keeping the fade
 * out of color attributes lets new geometry appear immediately after teardown.
 */
export const update_dendro_tree_layers = (
  layers_mat,
  data,
  { opacity = 1, duration = 0 } = {}
) => {
  layers_mat.dendro_tree_background_layer = clone_layer(
    layers_mat.dendro_tree_background_layer,
    data.background,
    opacity,
    duration
  );
  layers_mat.row_dendro_tree_branches_layer = clone_layer(
    layers_mat.row_dendro_tree_branches_layer,
    data.row_branches,
    opacity,
    duration
  );
  layers_mat.col_dendro_tree_branches_layer = clone_layer(
    layers_mat.col_dendro_tree_branches_layer,
    data.col_branches,
    opacity,
    duration
  );
  layers_mat.dendro_tree_water_layer = clone_layer(
    layers_mat.dendro_tree_water_layer,
    data.water,
    opacity,
    duration
  );
  layers_mat.dendro_tree_cut_outline_layer = clone_layer(
    layers_mat.dendro_tree_cut_outline_layer,
    data.cut_outline,
    opacity,
    duration
  );
  layers_mat.dendro_tree_cut_layer = clone_layer(
    layers_mat.dendro_tree_cut_layer,
    data.cut,
    opacity,
    duration
  );
  layers_mat.dendro_tree_caption_layer = clone_layer(
    layers_mat.dendro_tree_caption_layer,
    data.caption,
    opacity,
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
