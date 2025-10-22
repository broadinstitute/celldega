import { TileLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import {
  create_get_tile_data,
  create_render_tile_sublayers,
} from '../utils/tiles';

import { make_simple_image_layer } from './simple_image_layer';

const make_image_layer = (viz_state, info) => {
  const { max_pyramid_zoom } = viz_state.img.landscape_parameters;

  const opacity = 5;

  const image_layer = new TileLayer({
    id: info.button_name,
    tileSize: viz_state.dimensions.tileSize,
    refinementStrategy: 'no-overlap',
    minZoom: -7,
    maxZoom: 0,
    maxCacheSize: 20,
    extent: [0, 0, viz_state.dimensions.width, viz_state.dimensions.height],
    getTileData: create_get_tile_data(
      viz_state.global_base_url,
      info.name,
      viz_state.img.image_format,
      max_pyramid_zoom,
      options,
      viz_state.aws
    ),
    renderSubLayers: create_render_tile_sublayers(
      viz_state.dimensions,
      info.color,
      opacity
    ),
  });
  return image_layer;
};

export const make_image_layers = async (viz_state) => {
  const { image_info } = viz_state.img;

  if (
    image_info.length === 1 &&
    (image_info[0].name === 'h_and_e' || image_info[0].name === 'h&e')
  ) {
    const layer = await make_simple_image_layer(viz_state, image_info[0]);
    return [layer];
  }

  const image_layers = image_info.map((info) =>
    make_image_layer(viz_state, info)
  );
  return image_layers;
};

export const toggle_visibility_image_layers = (layers_obj, visible) => {
  layers_obj.image_layers = layers_obj.image_layers.map((layer) =>
    layer.clone({
      visible,
    })
  );
};

export const toggle_visibility_single_image_layer = (
  layers_obj,
  name,
  visible
) => {
  layers_obj.image_layers = layers_obj.image_layers.map((layer) =>
    layer.id.startsWith(name) ? layer.clone({ visible }) : layer
  );
};

export const update_opacity_single_image_layer = (
  viz_state,
  layers_obj,
  name,
  opacity,
  image_layer_colors
) => {
  const color = image_layer_colors[name];

  layers_obj.image_layers = layers_obj.image_layers.map((layer) =>
    layer.id.startsWith(name)
      ? layer.clone({
          renderSubLayers: create_render_tile_sublayers(
            viz_state.dimensions,
            color,
            opacity
          ),
          id: `${name}-${opacity}`,
        })
      : layer
  );
};
