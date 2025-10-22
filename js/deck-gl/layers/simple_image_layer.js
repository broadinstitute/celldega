import { TileLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import {
  create_simple_render_tile_sublayers,
  create_get_tile_data,
} from '../utils/tiles';

export const make_simple_image_layer = async (viz_state, info) => {
  const { global_base_url } = viz_state;
  const { dimensions } = viz_state;
  const { landscape_parameters } = viz_state.img;
  const { image_format } = viz_state.img.landscape_parameters;

  const simple_image_layer = new TileLayer({
    id: 'global-simple-image-layer',
    tileSize: dimensions.tileSize,
    refinementStrategy: 'no-overlap',
    minZoom: -7,
    maxZoom: 0,
    maxCacheSize: 20,
    extent: [0, 0, dimensions.width, dimensions.height],
    getTileData: create_get_tile_data(
      global_base_url,
      info.name,
      image_format,
      landscape_parameters.max_pyramid_zoom,
      options,
      viz_state.aws
    ),
    renderSubLayers: create_simple_render_tile_sublayers(dimensions),
    visible: true,
  });

  return simple_image_layer;
};

export const simple_image_layer_visibility = (layers_sst, visible) => {
  layers_sst.simple_image_layer = layers_sst.simple_image_layer.clone({
    visible,
  });
};
