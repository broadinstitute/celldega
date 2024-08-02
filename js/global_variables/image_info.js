export let image_format

export let image_info

export let image_layer_colors = {}

export const set_image_format = (format) => {
    image_format = format

    console.log('image format', image_format)
}

export const set_image_info = (info) => {
    image_info = info
}

export const set_image_layer_colors = () => {
    image_info.forEach(info => {
        image_layer_colors[info.button_name] = info.color;
    });
}