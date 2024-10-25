// import { simple_image_layer } from "../deck-gl/simple_image_layer"
import { square_scatter_layer_opacity } from "../deck-gl/square_scatter_layer"
// import { layers_sst, update_layers_sst } from "../deck-gl/layers_sst"
import { update_trx_layer_radius } from "../deck-gl/trx_layer"
import { update_opacity_single_image_layer } from "../deck-gl/image_layers"
import { update_cell_layer_radius } from "../deck-gl/cell_layer"
// import { deck_sst } from "../deck-gl/deck_sst"
import { get_layers_list } from "../deck-gl/layers_ist"

export const make_slider = () => {
    return  document.createElement("input")
}

export const set_image_layer_sliders = (img) => {

    img.image_layer_sliders = img.image_info.map( info => {
        let input = document.createElement("input")
        input.name = info.button_name
        return input
    })

}

const tile_slider_callback = async (deck_sst, viz_state, layers_sst) => {

    square_scatter_layer_opacity(layers_sst, viz_state.sliders.tile.value / 100)
    deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})

    console.log('setting props')
}

const cell_slider_callback = async (deck_ist, layers_obj, viz_state) => {

    const scale_down_cell_radius = 5

    update_cell_layer_radius(layers_obj, viz_state.sliders.cell.value / scale_down_cell_radius)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}

const trx_slider_callback = async (deck_ist, layers_obj, viz_state) => {

    const scale_down_trx_radius = 100

    update_trx_layer_radius(layers_obj, viz_state.sliders.trx.value/scale_down_trx_radius)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})
}

export const make_img_layer_slider_callback = (name, deck_ist, layers_obj, viz_state) => {
    return async () => {

        let inst_slider = viz_state.img.image_layer_sliders.filter(slider => slider.name === name)[0]

        // Get the slider value from the event
        const opacity = inst_slider.value/10

        // Use the slider value to update the opacity
        update_opacity_single_image_layer(viz_state, layers_obj, name, opacity, viz_state.img.image_layer_colors);

        const layers_list = get_layers_list(layers_obj, viz_state.close_up)
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

export const ini_slider = (slider_type, inst_deck, layers_obj, viz_state) => {

    let ini_value
    let callback

    let slider = make_slider()

    switch (slider_type) {
        case 'tile':
            ini_value = 100
            // may want to debouce later
            callback = () => tile_slider_callback(inst_deck, viz_state, layers_obj)
            break
        case 'cell':
            ini_value = viz_state.genes.trx_ini_raidus * 100
            callback = () => cell_slider_callback(inst_deck, layers_obj, viz_state)
            break
        case 'trx':
            ini_value = viz_state.genes.trx_ini_raidus * 100
            callback = () => trx_slider_callback(inst_deck, layers_obj, viz_state)
            break

        default:
            console.log('no match', slider_type)
    }

    ini_slider_params(slider, ini_value, callback)

    // save the slider to viz_state with a property name of slider_type
    viz_state.sliders[slider_type] = slider

}

export const toggle_slider = (slider, state) => {
    slider.disabled = !state
}