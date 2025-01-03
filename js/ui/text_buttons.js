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
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers'
import { toggle_dendro_layer_visibility } from '../deck-gl/matrix/dendro_layers'

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

const reorder_button_callback = (event, axis, deck_mat, layers_mat, viz_state) => {

    const current = d3.select(event.currentTarget)

    let button_name = current.text().toLowerCase()

    // quick fix for naming mismatch
    if (button_name === 'var') {
        button_name = 'rankvar'
    } else if (button_name === 'sum') {
        button_name = 'rank'
    }

    const is_active = current.classed('active')

    if (is_active === false) {

        current.classed('active', true)

        d3.select(viz_state.el)
          .selectAll('.button-' + axis)
          .classed('active', false)
          .style('border-color', viz_state.buttons.gray)

        current
            .style('border-color', viz_state.buttons.blue)
            .classed('active', true)

        viz_state.order.current[axis] = button_name


        layers_mat.mat_layer = layers_mat.mat_layer.clone({
            updateTriggers: {
                getPosition: [viz_state.order.current.row, viz_state.order.current.col]
            }
        })

        if (axis === 'row') {
            layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
                updateTriggers: {
                    getPosition: viz_state.order.current.row
                }
            })
        } else {
            layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
                updateTriggers: {
                    getPosition: viz_state.order.current.col
                }
            })
        }

        toggle_dendro_layer_visibility(layers_mat, viz_state, axis)

        deck_mat.setProps({
            layers: get_mat_layers_list(layers_mat),
        })

    }


}

export const make_reorder_button = (container, text, active, width=40, axis, deck_mat, layers_mat, viz_state) => {

    let button_class = 'button-' + axis


    let color
    if (active === true) {
        color = viz_state.buttons.blue
    } else {
        color = viz_state.buttons.gray
    }

    // make text all caps
    text = text.toUpperCase()

    d3.select(container)
        .append('div')
        .classed(button_class, true)
        .classed('active', active)
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
        .style('color', '#47515b')
        .style('border', '3px solid')  // Light gray border
        .style('border-color', color)  // Light gray border
        .style('border-radius', '12px')  // Rounded corners
        .style('margin-top', '5px')
        .style('margin-left', '5px')
        .style('padding', '4px 10px')  // Padding inside the button
        .style('user-select', 'none')
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')
        .on('click', (event) => reorder_button_callback(event, axis, deck_mat, layers_mat, viz_state))


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

export const make_edit_button = (deck_ist, layers_obj, viz_state, container, text, width, edit_button_callback) => {

    let button_class = 'edit_button'

    const active = false

    // make text all caps
    text = text.toUpperCase()

    const inst_button = d3.select(container)
        .append('div')
        .classed(button_class, true)
        .classed('active', active)
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
        .style('color', 'gray')
        // .style('border', '3px solid')  // Light gray border
        // .style('border-color', color)  // Light gray border
        // .style('border-radius', '12px')  // Rounded corners
        // .style('margin-top', '5px')
        .style('margin-left', '3px')
        // .style('padding', '4px 10px')  // Padding inside the button
        .style('user-select', 'none')
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')
        .on('click', (event) => edit_button_callback(event, deck_ist, layers_obj, viz_state))
        .node()

    const button_name = text.toLowerCase()
    viz_state.edit.buttons[button_name] = inst_button

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
