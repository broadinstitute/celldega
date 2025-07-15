import { load } from '@loaders.gl/core';
import { ImageLoader } from '@loaders.gl/images';
import { BitmapLayer } from 'deck.gl';
import * as mathGl from 'math.gl';

import { handleAsyncError } from '../../temp_utils/errorHandler';
import { CustomBitmapLayer } from '../layers/CustomBitmapLayer';

/**
 * Creates a function to fetch tile data for deck.gl TileLayer
 * @param {string} base_url - Base URL for tile requests
 * @param {string} image_name - Name of the image pyramid
 * @param {string} image_format - File format (e.g., '.png', '.jpg')
 * @param {number} max_image_zoom - Maximum zoom level of the pyramid
 * @param {Object} options - Additional fetch options
 * @param {Object} aws - AWS credentials for signed requests
 * @returns {Function} Async function that fetches tile data
 */
export const create_get_tile_data = (
  base_url,
  image_name,
  image_format,
  max_image_zoom,
  options = {},
  aws = null
) => {
  return async ({ index }) => {
    const { x, y, z } = index;
    const full_url = `${base_url}/pyramid_images/${image_name}_files/${max_image_zoom + z}/${x}_${y}${image_format}`;

    // Separate fetch options so we can merge them with loader options
    const { fetch: fetchOptions = {}, ...loaderOptions } = options;

    // Fetch function that preserves headers and supports aws signed requests
    const fetch_fn = async (url, fetchOpts = {}) => {
      const merged = { ...fetchOptions, ...fetchOpts };
      if (aws) {
        return aws.fetch(url, merged);
      }
      return fetch(url, merged);
    };

    try {
      const image = await load(full_url, ImageLoader, {
        ...loaderOptions,
        fetch: fetch_fn,
      });
      return image;
    } catch (error) {
      const result = handleAsyncError(error, {
        coordinates: `${x},${y},${z}`,
        url: full_url,
        messages: {
          network: 'Failed to load tile due to network issues',
          notFound: 'Tile does not exist',
          unauthorized: 'Unauthorized access to tile',
          forbidden: 'Access forbidden for tile',
          unexpected: 'Failed to load tile',
        },
        throwOnAuth: true, // Auth errors will throw
        logUnexpected: true, // Unexpected errors will be logged
      });

      // Handle 404s silently (common for sparse tilesets)
      if (result.error === 'not_found') {
        return null;
      }

      // For network errors, return null but could implement retry logic
      if (result.error === 'network') {
        return null;
      }

      // For other unexpected errors, return null
      return null;
    }
  };
};

/**
 * Creates a render function for tile sublayers with custom color and opacity
 * @param {Object} dimensions - Canvas dimensions {width, height}
 * @param {Array} color - RGB color array [r, g, b]
 * @param {number} opacity - Opacity scale factor
 * @returns {Function} Render function for TileLayer
 */
export const create_render_tile_sublayers =
  (dimensions, color, opacity) => (props) => {
    const {
      bbox: { left, bottom, right, top },
    } = props.tile;

    const { width, height } = dimensions;

    return new CustomBitmapLayer(props, {
      data: null,
      image: props.data,
      bounds: [
        mathGl.clamp(left, 0, width),
        mathGl.clamp(bottom, 0, height),
        mathGl.clamp(right, 0, width),
        mathGl.clamp(top, 0, height),
      ],
      color,
      opacityScale: opacity,
    });
  };

/**
 * Creates a simple render function for tile sublayers without custom styling
 * @param {Object} dimensions - Canvas dimensions {width, height}
 * @returns {Function} Simple render function for TileLayer
 */
export const create_simple_render_tile_sublayers = (dimensions) => (props) => {
  const {
    bbox: { left, bottom, right, top },
  } = props.tile;
  const { width, height } = dimensions;

  return new BitmapLayer(props, {
    data: null,
    image: props.data,
    bounds: [
      mathGl.clamp(left, 0, width),
      mathGl.clamp(bottom, 0, height),
      mathGl.clamp(right, 0, width),
      mathGl.clamp(top, 0, height),
    ],
  });
};
