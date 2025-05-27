import { load } from '@loaders.gl/core';
import { ImageLoader } from '@loaders.gl/images';

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
        const fetch_fn = aws ? (url, fetchOptions) => aws.fetch(url, fetchOptions) : undefined;

        try {
            const image = await load(full_url, ImageLoader, {
                ...options,
                fetch: fetch_fn
            });
            return image;
        } catch (error) {
            console.error('Failed to load tile:', error);
            return null;
        }
    };
};
