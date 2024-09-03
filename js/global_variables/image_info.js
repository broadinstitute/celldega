
export let image_layer_colors = {}

export const set_image_format = (img, format) => {
    img.image_format = format
}

export const set_image_info = (img, info) => {
    img.image_info = info
}

export const set_image_layer_colors = (image_info) => {
    image_info.forEach(info => {
        image_layer_colors[info.button_name] = info.color;
    });
}