import { load } from '@loaders.gl/core';
import { ImageLoader } from '@loaders.gl/images';
import { handleAsyncError } from '../temp_utils/errorHandler';

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

    // If AWS credentials are provided, use aws.fetch to sign the request
    const fetch_fn = aws
      ? (url, fetchOptions) => aws.fetch(url, fetchOptions)
      : undefined;

    try {
      const image = await load(full_url, ImageLoader, {
        ...options,
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
