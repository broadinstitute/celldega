export let image_info

export let image_layer_colors = {}

export const set_image_info = (info) => {
    image_info = info
}

export const set_image_layer_colors = (info) => {
    image_info.forEach(info => {
        image_layer_colors[info.button_name] = info.color;
    });    
}