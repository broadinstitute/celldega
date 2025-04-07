import { load } from '@loaders.gl/core';
import { ImageLoader } from '@loaders.gl/images';

export const create_get_tile_data = (base_url, image_name, image_format, max_image_zoom, options, aws = null) => {
    return async ({ index }) => {
        const { x, y, z } = index;
        const full_url = `${base_url}/pyramid_images/${image_name}_files/${max_image_zoom + z}/${x}_${y}${image_format}`;

        try {
            if (aws !== null) {
                const response = await aws.fetch(full_url);
                const arrayBuffer = await response.arrayBuffer();

                return await load(arrayBuffer, {
                    loader: ImageLoader,
                    mimeType: 'image/webp',
                    ...options
                });
            } else {
                return await load(full_url, {
                    loader: ImageLoader,
                    ...options
                });
            }

        } catch (error) {
            console.error('Failed to load tile:', error);
            return null;
        }
    };
};
