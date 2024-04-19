import { load } from '@loaders.gl/core';

export const create_get_tile_data = (base_url, image_name, max_image_zoom, options) => {
    return ({ index }) => {
        const { x, y, z } = index;
        const full_url = `${base_url}/pyramid_images/${image_name}_files/${max_image_zoom + z}/${x}_${y}.jpeg`;

        return load(full_url, options).then(data => {
            return data;
        }).catch(error => {
            console.error('Failed to load tile:', error);
            return null;
        });
    };
};