import { TileLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import { getModelMatrixProps } from '../../utils/rotation';
import {
  create_get_tile_data,
  create_render_tile_sublayers,
} from '../utils/tiles';

import { make_simple_image_layer } from './simple_image_layer';

const make_image_layer = (viz_state, info, datasetIndex = 0, cacheKey = '') => {
  const { max_pyramid_zoom } = viz_state.img.landscape_parameters;

  const opacity = 5;

  // Include dataset index and cache key in ID to force complete layer recreation
  const layerId = `${info.button_name}-ds${datasetIndex}${cacheKey ? `-${cacheKey}` : ''}`;

  const image_layer = new TileLayer({
    id: layerId,
    tileSize: viz_state.dimensions.tileSize,
    refinementStrategy: 'no-overlap',
    minZoom: -7,
    maxZoom: 0,
    maxCacheSize: 0, // Disable internal tile caching
    maxRequests: 6, // Limit concurrent tile requests
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
    ...getModelMatrixProps(viz_state.rotation),
  });
  return image_layer;
};

export const make_image_layers = async (viz_state, datasetIndex = 0) => {
  const { image_info } = viz_state.img;

  // Generate a unique cache key to force complete layer recreation
  const cacheKey = Date.now().toString(36);

  if (
    image_info.length === 1 &&
    (image_info[0].name === 'h_and_e' || image_info[0].name === 'h&e')
  ) {
    const layer = await make_simple_image_layer(viz_state, image_info[0], datasetIndex, cacheKey);
    return [layer];
  }

  const image_layers = image_info.map((info) =>
    make_image_layer(viz_state, info, datasetIndex, cacheKey)
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

/**
 * Create image layers for yearbook.
 * Creates one set of image layers per portrait, each with its own extent.
 * This ensures tiles are loaded correctly for each discontiguous region.
 *
 * @param {Object} viz_state - Visualization state
 * @param {Array<{cell_id: string, x: number, y: number}>} portrait_centers - Portrait centers
 * @param {number} portrait_data_size - Portrait size in data coordinates
 * @param {string} cacheKey - Cache key for layer IDs (page-based for reuse)
 * @returns {Array} Image layers for all portraits
 */
export const make_yearbook_image_layers = async (viz_state, portrait_centers, portrait_data_size, cacheKey = null) => {
  const { image_info } = viz_state.img;
  const { max_pyramid_zoom, tile_size } = viz_state.img.landscape_parameters;
  const layerCacheKey = cacheKey || Date.now().toString(36);

  const all_layers = [];
  const half_size = portrait_data_size / 2;
  // Padding should be generous to cover zoomed-in views and tile boundaries
  const padding = Math.max(tile_size * 3, portrait_data_size * 0.5);

  console.log(`Yearbook: Creating image layers for ${portrait_centers.length} portraits, data_size=${portrait_data_size.toFixed(0)}, padding=${padding.toFixed(0)}`);

  portrait_centers.forEach((center, portrait_index) => {
    // Each portrait gets its own extent covering its visible area plus padding
    const extent = [
      Math.max(0, center.x - half_size - padding),
      Math.max(0, center.y - half_size - padding),
      Math.min(viz_state.dimensions.width, center.x + half_size + padding),
      Math.min(viz_state.dimensions.height, center.y + half_size + padding),
    ];

    image_info.forEach((info) => {
      const opacity = 5;
      // Include portrait index in layer ID for proper updates
      const layerId = `yb-${info.button_name}-p${portrait_index}-${layerCacheKey}`;

      const image_layer = new TileLayer({
        id: layerId,
        tileSize: viz_state.dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 50,
        maxRequests: 6,
        extent: extent,
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
        ...getModelMatrixProps(viz_state.rotation),
      });

      all_layers.push(image_layer);
    });
  });

  console.log(`Yearbook: Created ${all_layers.length} image layers total`);
  return all_layers;
};
