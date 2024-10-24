import { load } from '@loaders.gl/core';

export const create_get_tile_data = (base_url, image_name, image_format, max_image_zoom, options) => {

    console.log('create_get_tile_data')
    console.log('base_url', base_url)
    console.log('image_name', image_name)
    console.log('image_format', image_format)
    console.log('max_image_zoom', max_image_zoom)
    console.log('options', options)


    return ({ index }) => {
        const { x, y, z } = index;
        const full_url = `${base_url}/pyramid_images/${image_name}_files/${max_image_zoom + z}/${x}_${y}${image_format}`;

        return load(full_url, options).then(data => {
            return data;
        }).catch(error => {
            console.error('Failed to load tile:', error);
            return null;
        });
    };
};