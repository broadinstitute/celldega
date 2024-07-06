import * as d3 from 'd3'
import { simple_image_layer, simple_image_layer_visibility } from '../deck-gl/simple_image_layer'
import { square_scatter_layer, square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer'
import { layers_sst, update_layers_sst } from '../deck-gl/layers_sst'

import { image_layers, toggle_visibility_image_layers, toggle_visibility_single_image_layer } from '../deck-gl/image_layers'
import { deck_sst } from '../deck-gl/deck_sst'
import { deck_ist } from '../deck-gl/deck_ist'

import { background_layer, toggle_background_layer_visibility } from '../deck-gl/background_layer'
import { path_layer, toggle_path_layer_visibility } from '../deck-gl/path_layer'
import { cell_layer, toggle_cell_layer_visibility } from '../deck-gl/cell_layer'
import { trx_layer, toggle_trx_layer_visibility } from '../deck-gl/trx_layer'
import { layers, update_layers } from '../deck-gl/layers'

import { tile_slider, cell_slider, trx_slider, toggle_slider} from './sliders'

console.log('text_buttons')

let is_visible

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

export const make_button = (container, technology, text, color='blue') => {

    let callback

    if (text === 'IMG') {
        if (technology === 'sst'){
            callback = sst_img_button_callback
        } else {
            callback = ist_img_button_callback
        }
    } else if (text === 'TILE') {
        callback =  tile_button_callback
    } else if (text === 'TRX'){
        callback = trx_button_callback_ist
    } else if (text === 'CELL'){
        callback = cell_button_callback
    } else {
        callback = make_ist_img_layer_button_callback(text)
    }
    
    d3.select(container)
        .append('div')
        .attr('class', 'button')
        .text(text)
        .style('width', '40px')
        .style('text-align', 'left')
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', color)
        .style('margin-top', '5px')
        .style('margin-left', '5px')
        .style('user-select', 'none')
        .on('click', callback)  
        
}


const make_ist_img_layer_button_callback = (text) => {
    return async (event) => {

        toggle_visible_button(event)

        toggle_visibility_single_image_layer(text, is_visible)

        let new_layers = [
            background_layer,
            ...image_layers, 
            path_layer, 
            cell_layer, 
            trx_layer
        ]
    
        update_layers(new_layers)
        deck_ist.setProps({layers})   

        console.log('Button clicked:', text)
    }
}

const ist_img_layer_button_callback = async (event) => {
    toggle_visible_button(event)

    console.log(image_layers.map(x => x.id))

    console.log('here')
}


const sst_img_button_callback = async (event) => {

    toggle_visible_button(event)

    simple_image_layer_visibility(is_visible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst})

}

const ist_img_button_callback = async (event) => {

    toggle_visible_button(event)
    toggle_visibility_image_layers(is_visible)
    toggle_background_layer_visibility(is_visible)

    let new_layers = [
        background_layer,
        ...image_layers, 
        path_layer, 
        cell_layer, 
        trx_layer
    ]

    update_layers(new_layers)
    deck_ist.setProps({layers})

}

const trx_button_callback_ist = async (event) => {

    toggle_visible_button(event)

    toggle_slider(trx_slider, is_visible)

    toggle_trx_layer_visibility(is_visible)

    let new_layers = [
        background_layer,
        ...image_layers, 
        path_layer, 
        cell_layer, 
        trx_layer
    ]

    update_layers(new_layers)
    deck_ist.setProps({layers})   

}

const tile_button_callback = async (event) => {

    toggle_visible_button(event)

    toggle_slider(tile_slider, is_visible)

    square_scatter_layer_visibility(is_visible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst})

}    

const cell_button_callback = async (event) => {

    toggle_visible_button(event)

    toggle_slider(cell_slider, is_visible)

    toggle_cell_layer_visibility(is_visible)
    toggle_path_layer_visibility(is_visible)    

    let new_layers = [
        background_layer,
        ...image_layers, 
        path_layer, 
        cell_layer, 
        trx_layer
    ]

    update_layers(new_layers)
    deck_ist.setProps({layers})    
}
