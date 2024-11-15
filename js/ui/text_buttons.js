import * as d3 from 'd3'
import { simple_image_layer_visibility } from '../deck-gl/simple_image_layer'
import { square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer'
// import { layers_sst, update_layers_sst } from '../deck-gl/layers_sst'
import { toggle_visibility_image_layers, toggle_visibility_single_image_layer } from '../deck-gl/image_layers'
// import { deck_sst } from '../deck-gl/deck_sst'
import { toggle_background_layer_visibility } from '../deck-gl/background_layer'
import { toggle_path_layer_visibility } from '../deck-gl/path_layer'
import { new_toggle_cell_layer_visibility } from '../deck-gl/cell_layer'
import { toggle_trx_layer_visibility } from '../deck-gl/trx_layer'
import { get_layers_list } from '../deck-gl/layers_ist'
import { toggle_slider } from './sliders'

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

export const make_reorder_button = (container, text, color='blue', width=40, button_class='button', deck_mat, layers_mat, viz_state) => {

    let callback = async (event) => {
        console.log('reorder button clicked')
    }

    // make text all caps
    text = text.toUpperCase()

    // d3.select(container)
    //     .append('div')
    //     .attr('class', button_class)
    //     .text(text)
    //     .style('width', width + 'px')
    //     .style('text-align', 'center')
    //     .style('cursor', 'pointer')
    //     .style('font-size', '12px')
    //     .style('font-weight', 'bold')
    //     .style('color', color)
    //     .style('margin-top', '5px')
    //     .style('margin-left', '5px')
    //     .style('user-select', 'none')
    //     .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif;')
    //     .on('click', callback)


    d3.select(container)
        .append('div')
        .attr('class', button_class)
        .text(text)
        .style('width', width + 'px')
        .style('height', '20px')  // Adjust height for button padding
        .style('display', 'inline-flex')
        .style('align-items', 'center')
        .style('justify-content', 'center')
        .style('text-align', 'center')
        .style('cursor', 'pointer')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        // .style('color', color)
        .style('color', '#47515b')
        // .style('background-color', '#f0f0f0')  // Light background color
        // .style('border', '2px solid #b3b3b3')  // Light gray border
        .style('border', '3px solid')  // Light gray border
        .style('border-color', color)  // Light gray border
        .style('border-radius', '12px')  // Rounded corners
        .style('margin-top', '5px')
        .style('margin-left', '5px')
        .style('padding', '4px 10px')  // Padding inside the button
        .style('user-select', 'none')
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')
        .on('click', callback)


}

export const make_button = (container, technology, text, color='blue', width=40, button_class='button', inst_deck, layers_obj, viz_state) => {

    let callback

    // define callback - can be cleaned up to enforce common arguments

    if (text === 'IMG') {
        if (technology === 'sst'){
            callback = (event) => sst_img_button_callback(event, inst_deck, layers_obj)
        } else {
            callback = (event) => ist_img_button_callback(event, inst_deck, layers_obj, viz_state)
        }
    } else if (text === 'TILE') {
        callback = (event) => tile_button_callback(event, inst_deck, layers_obj, viz_state)
    } else if (text === 'TRX'){
        callback = (event) => trx_button_callback_ist(event, inst_deck, layers_obj, viz_state)
    } else if (text === 'CELL'){
        callback = (event) => cell_button_callback(event, inst_deck, layers_obj, viz_state)
    } else {
        callback = make_ist_img_layer_button_callback(text, inst_deck, layers_obj, viz_state)
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

            let inst_slider = viz_state.img.image_layer_sliders.filter(slider => slider.name === text)[0]

            toggle_slider(inst_slider, is_visible)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

        }

    }
}

const sst_img_button_callback = async (event, deck_sst, layers_sst) => {

    toggle_visible_button(event)

    simple_image_layer_visibility(layers_sst, is_visible)

    deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})

}

const ist_img_button_callback = async (event, deck_ist, layers_obj, viz_state) => {

    toggle_visible_button(event)
    toggle_visibility_image_layers(layers_obj, is_visible)
    toggle_background_layer_visibility(layers_obj, is_visible)

    d3.select(viz_state.containers.image)
        .selectAll('.img_layer_button')
        .style('color', is_visible ? 'blue' : 'gray');

    set_img_layer_visible(is_visible)

    viz_state.img.image_layer_sliders.map(slider => toggle_slider(slider, is_visible))

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}

const trx_button_callback_ist = async (event, deck_ist, layers_obj, viz_state) => {

    toggle_visible_button(event)

    toggle_slider(viz_state.genes.trx_slider, is_visible)

    toggle_trx_layer_visibility(layers_obj, is_visible)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}

const tile_button_callback = async (event, deck_sst, layers_sst, viz_state) => {

    toggle_visible_button(event)

    toggle_slider(viz_state.sliders.tile, is_visible)

    square_scatter_layer_visibility(layers_sst, is_visible)

    deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})

}

const cell_button_callback = async (event, deck_ist, layers_obj, viz_state) => {

    toggle_visible_button(event)

    toggle_slider(viz_state.sliders.cell, is_visible)

    new_toggle_cell_layer_visibility(layers_obj, is_visible)
    toggle_path_layer_visibility(layers_obj, is_visible)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})
}
