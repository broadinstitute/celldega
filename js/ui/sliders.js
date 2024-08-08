import { simple_image_layer } from "../deck-gl/simple_image_layer"
import { square_scatter_layer, square_scatter_layer_opacity } from "../deck-gl/square_scatter_layer"
import { layers_sst, update_layers_sst } from "../deck-gl/layers_sst"
import { update_trx_layer_radius } from "../deck-gl/trx_layer"
import { update_opacity_single_image_layer } from "../deck-gl/image_layers"
import { update_cell_layer_radius } from "../deck-gl/cell_layer"
import { deck_sst } from "../deck-gl/deck_sst"
import { trx_ini_raidus } from "../global_variables/trx_ini_raidus"
import { close_up } from "../global_variables/close_up"
import { get_layers_list } from "../deck-gl/layers_ist"

export let tile_slider = document.createElement("input")
export let cell_slider = document.createElement("input")
export let trx_slider = document.createElement("input")

export let image_layer_sliders

export const set_image_layer_sliders = (image_info) => {

    image_layer_sliders = image_info.map( info => {
        let input = document.createElement("input")
        input.name = info.button_name
        return input
    })

}

const tile_slider_callback = async () => {
    square_scatter_layer_opacity(tile_slider.value / 100)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst})
}

const cell_slider_callback = async (deck_ist, layers_obj, viz_state) => {

    const scale_down_cell_radius = 5

    update_cell_layer_radius(layers_obj, cell_slider.value / scale_down_cell_radius)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}

const trx_slider_callback = async (deck_ist, layers_obj, viz_state) => {

    const scale_down_trx_radius = 100

    update_trx_layer_radius(layers_obj, trx_slider.value/scale_down_trx_radius)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})
}

export const make_img_layer_slider_callback = (name, deck_ist, layers_obj) => {
    return async () => {

        let inst_slider = image_layer_sliders.filter(slider => slider.name === name)[0]

        // Get the slider value from the event
        const opacity = inst_slider.value/10

        // Use the slider value to update the opacity
        update_opacity_single_image_layer(layers_obj, name, opacity);

        const layers_list = get_layers_list(layers_obj, close_up)
        deck_ist.setProps({layers: layers_list})
    };
};

export const ini_slider_params = (slider, ini_value, callback) =>{

    slider.type = "range"
    slider.min = "0"
    slider.max = "100"
    slider.value = ini_value
    slider.className = "slider"
    slider.style.width = "75px"
    slider.addEventListener("input", callback)

}

export const ini_slider = (slider_type, deck_ist, layers_obj, viz_state) => {

    let slider
    let ini_value
    let callback

    switch (slider_type) {
        case 'tile':
            slider = tile_slider
            ini_value = 100
            callback = tile_slider_callback
            break
        case 'cell':
            slider = cell_slider
            ini_value = trx_ini_raidus * 100
            callback = () => cell_slider_callback(deck_ist, layers_obj, viz_state)
            break
        case 'trx':
            slider = trx_slider
            ini_value = trx_ini_raidus * 100
            callback = () => trx_slider_callback(deck_ist, layers_obj)
            break

        default:
            console.log('no match', slider_type)
    }

    ini_slider_params(slider, ini_value, callback)
}

export const toggle_slider = (slider, state) => {
    slider.disabled = !state
}