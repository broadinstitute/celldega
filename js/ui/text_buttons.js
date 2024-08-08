import * as d3 from 'd3'
import { simple_image_layer, simple_image_layer_visibility } from '../deck-gl/simple_image_layer'
import { square_scatter_layer, square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer'
import { layers_sst, update_layers_sst } from '../deck-gl/layers_sst'
import { toggle_visibility_image_layers, toggle_visibility_single_image_layer } from '../deck-gl/image_layers'
import { deck_sst } from '../deck-gl/deck_sst'
import { toggle_background_layer_visibility } from '../deck-gl/background_layer'
import { toggle_path_layer_visibility } from '../deck-gl/path_layer'
import { new_toggle_cell_layer_visibility } from '../deck-gl/cell_layer'
import { toggle_trx_layer_visibility } from '../deck-gl/trx_layer'
import { get_layers_list } from '../deck-gl/layers_ist'
import { tile_slider, cell_slider, trx_slider, toggle_slider, image_layer_sliders } from './sliders'

let is_visible

let img_layer_visible = true

const set_img_layer_visible = (visible) => {
    img_layer_visible = visible
}

const toggle_visible_button = (event) => {
    const current = d3.select(event.currentTarget)

    if (current.style('color') === 'blue') {
        current.style('color', 'gray')
        is_visible = false
    } else {
        current.style('color', 'blue')
        is_visible = true
    }

    return is_visible
}

export const make_button = (container, technology, text, color='blue', width=40, button_class='button', deck_ist, layers_obj, viz_state) => {

    let callback

    if (text === 'IMG') {
        if (technology === 'sst'){
            callback = sst_img_button_callback
        } else {
            callback = () => ist_img_button_callback(event, deck_ist, layers_obj, viz_state)
        }
    } else if (text === 'TILE') {
        callback = () => tile_button_callback(event, deck_ist)
    } else if (text === 'TRX'){
        callback = () => trx_button_callback_ist(event, deck_ist, layers_obj, viz_state)
    } else if (text === 'CELL'){
        callback = () => cell_button_callback(event, deck_ist, layers_obj, viz_state)
    } else {
        callback = make_ist_img_layer_button_callback(text, deck_ist, layers_obj, viz_state)
    }

    d3.select(container)
        .append('div')
        .attr('class', button_class)
        .text(text)
        .style('width', width + 'px')
        .style('text-align', 'left')
        .style('cursor', 'pointer')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .style('color', color)
        .style('margin-top', '5px')
        .style('margin-left', '5px')
        .style('user-select', 'none')
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif;')
        .on('click', callback)

}


const make_ist_img_layer_button_callback = (text, deck_ist, layers_obj, viz_state) => {

    return async (event) => {

        if (img_layer_visible){

            toggle_visible_button(event)

            toggle_visibility_single_image_layer(layers_obj, text, is_visible)

            let inst_slider = image_layer_sliders.filter(slider => slider.name === text)[0]

            toggle_slider(inst_slider, is_visible)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

        }

    }
}

const sst_img_button_callback = async (event) => {

    toggle_visible_button(event)

    simple_image_layer_visibility(is_visible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({
        layers: layers_sst
    })

}

const ist_img_button_callback = async (event, deck_ist, layers_obj, viz_state) => {

    toggle_visible_button(event)
    toggle_visibility_image_layers(layers_obj, is_visible)
    toggle_background_layer_visibility(layers_obj, is_visible)

    d3.select(viz_state.image_container)
        .selectAll('.img_layer_button')
        .style('color', is_visible ? 'blue' : 'gray');

    set_img_layer_visible(is_visible)

    image_layer_sliders.map(slider => toggle_slider(slider, is_visible))

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}

const trx_button_callback_ist = async (event, deck_ist, layers_obj, viz_state) => {

    toggle_visible_button(event)

    toggle_slider(trx_slider, is_visible)

    toggle_trx_layer_visibility(layers_obj, is_visible)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}

const tile_button_callback = async (event) => {

    toggle_visible_button(event)

    toggle_slider(tile_slider, is_visible)

    square_scatter_layer_visibility(is_visible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({
        layers: layers_sst
    })

}

const cell_button_callback = async (event, deck_ist, layers_obj, viz_state) => {

    toggle_visible_button(event)

    toggle_slider(cell_slider, is_visible)

    new_toggle_cell_layer_visibility(layers_obj, is_visible)
    toggle_path_layer_visibility(layers_obj, is_visible)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})
}
