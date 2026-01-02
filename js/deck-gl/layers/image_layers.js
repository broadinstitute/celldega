import { TileLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import { getModelMatrixProps } from '../../utils/rotation';
import {
  create_get_tile_data,
  create_render_tile_sublayers,
  create_simple_render_tile_sublayers,
} from '../utils/tiles';

import { make_simple_image_layer } from './simple_image_layer';

/**
 * Create a getTileData function that uses the parquet row group reader
 * @param {Object} imageReader - ImageRowGroupReader instance
 * @param {number} maxPyramidZoom - Maximum zoom level
 * @param {string} channelName - Channel name for logging
 * @returns {Function} - getTileData function for TileLayer
 */
const create_get_tile_data_from_parquet = (
  imageReader,
  maxPyramidZoom,
  channelName = 'unknown'
) => {
  let requestCount = 0;

  return async ({ index }) => {
    const { x, y, z } = index;
    // deck.gl uses negative z values, convert to actual zoom level
    const actualZoom = maxPyramidZoom + z;

    requestCount++;
    if (requestCount <= 3) {
      console.log(
        `[image_layers:${channelName}] Tile request #${requestCount}: x=${x}, y=${y}, z=${z} -> actualZoom=${actualZoom}`
      );
    }

    const blobUrl = await imageReader.readTile(actualZoom, x, y);

    if (!blobUrl) {
      if (requestCount <= 3) {
        console.log(`[image_layers:${channelName}] No tile data for ${actualZoom}/${x}_${y}`);
      }
      return null;
    }

    // Load the image from the blob URL
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        if (requestCount <= 3) {
          console.log(
            `[image_layers:${channelName}] Loaded tile ${actualZoom}/${x}_${y}: ${img.width}x${img.height}`
          );
        }
        resolve(img);
      };
      img.onerror = (err) => {
        console.error(`[image_layers:${channelName}] Failed to load tile image:`, err);
        reject(err);
      };
      img.src = blobUrl;
    });
  };
};

const make_image_layer = (viz_state, info, datasetIndex = 0, cacheKey = '') => {
  const { max_pyramid_zoom } = viz_state.img.landscape_parameters;

  const opacity = 5;

  // Include dataset index and cache key in ID to force complete layer recreation
  const layerId = `${info.button_name}-ds${datasetIndex}${cacheKey ? `-${cacheKey}` : ''}`;

  // Check if using row group mode and if we have a reader for this channel
  const useRowGroups = viz_state.use_row_groups;
  const imageReader = viz_state.row_group_readers?.images?.[info.name];

  // Choose the appropriate getTileData function
  let getTileData;
  if (useRowGroups && imageReader) {
    console.log(`[image_layers] Using parquet reader for ${info.name}, maxZoom=${max_pyramid_zoom}`);
    getTileData = create_get_tile_data_from_parquet(imageReader, max_pyramid_zoom, info.name);
  } else {
    getTileData = create_get_tile_data(
      viz_state.global_base_url,
      info.name,
      viz_state.img.image_format,
      max_pyramid_zoom,
      options,
      viz_state.aws
    );
  }

  const image_layer = new TileLayer({
    id: layerId,
    tileSize: viz_state.dimensions.tileSize,
    refinementStrategy: 'no-overlap',
    minZoom: -7,
    maxZoom: 0,
    maxCacheSize: 0, // Disable internal tile caching
    maxRequests: 6, // Limit concurrent tile requests
    extent: [0, 0, viz_state.dimensions.width, viz_state.dimensions.height],
    getTileData,
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
    const layer = await make_simple_image_layer(
      viz_state,
      image_info[0],
      datasetIndex,
      cacheKey
    );
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
export const make_yearbook_image_layers = async (
  viz_state,
  portrait_centers,
  portrait_data_size,
  cacheKey = null
) => {
  const { image_info } = viz_state.img;
  const { max_pyramid_zoom, tile_size } = viz_state.img.landscape_parameters;
  const layerCacheKey = cacheKey || Date.now().toString(36);

  const all_layers = [];
  const half_size = portrait_data_size / 2;
  // Padding should be generous to cover zoomed-in views and tile boundaries
  const padding = Math.max(tile_size * 3, portrait_data_size * 0.5);

  // Check if this is an H&E image (single image with h_and_e or h&e name)
  // H&E images should use simple rendering without color channel filtering
  const isHnE =
    image_info.length === 1 &&
    (image_info[0].name === 'h_and_e' || image_info[0].name === 'h&e');

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

      // Use simple rendering for H&E images (no color channel filtering)
      // This preserves the original RGB colors of histology images
      const renderSubLayers = isHnE
        ? create_simple_render_tile_sublayers(viz_state.dimensions)
        : create_render_tile_sublayers(viz_state.dimensions, info.color, opacity);

      const image_layer = new TileLayer({
        id: layerId,
        tileSize: viz_state.dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 50,
        maxRequests: 6,
        extent,
        getTileData: create_get_tile_data(
          viz_state.global_base_url,
          info.name,
          viz_state.img.image_format,
          max_pyramid_zoom,
          options,
          viz_state.aws
        ),
        renderSubLayers,
        ...getModelMatrixProps(viz_state.rotation),
      });

      all_layers.push(image_layer);
    });
  });

  return all_layers;
};
