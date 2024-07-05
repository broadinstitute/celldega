import * as d3 from 'd3'
import { simple_image_layer, simple_image_layer_visibility } from '../deck-gl/simple_image_layer'
import { square_scatter_layer, square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer'
import { layers_sst, update_layers_sst } from '../deck-gl/layers_sst'

import { image_layers, toggle_visibility_image_layers } from '../deck-gl/image_layers'
import { deck_sst } from '../deck-gl/deck_sst'
import { deck_ist } from '../deck-gl/deck_ist'

import { background_layer, toggle_background_layer_visibility } from '../deck-gl/background_layer'
import { path_layer, toggle_path_layer_visibility } from '../deck-gl/path_layer'
import { cell_layer, toggle_cell_layer_visibility } from '../deck-gl/cell_layer'
import { trx_layer, toggle_trx_layer_visibility } from '../deck-gl/trx_layer'
import { layers, update_layers } from '../deck-gl/layers'

import { tile_slider, cell_slider, trx_slider, toggle_slider} from './sliders'

let isVisible

const toggle_visible_button = (event) => {
    const current = d3.select(event.currentTarget)

    if (current.style('color') === 'blue') {
        current.style('color', 'gray')
        isVisible = false
    } else {
        current.style('color', 'blue')
        isVisible = true
    }

    return isVisible
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
    }
    
    d3.select(container)
        .append('div')
        .attr('class', 'button')
        .text(text)
        .style('width', '40px')
        .style('text-align', 'center')
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', color)
        .style('margin-top', '5px')
        .style('user-select', 'none')
        .on('click', callback)  
        
}

const sst_img_button_callback = async (event) => {

    toggle_visible_button(event)

    simple_image_layer_visibility(isVisible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst})

}

const ist_img_button_callback = async (event) => {

    toggle_visible_button(event)
    toggle_visibility_image_layers(isVisible)
    toggle_background_layer_visibility(isVisible)

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

    toggle_slider(trx_slider, isVisible)

    toggle_trx_layer_visibility(isVisible)

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

    toggle_slider(tile_slider, isVisible)

    square_scatter_layer_visibility(isVisible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst})

}    

const cell_button_callback = async (event) => {

    toggle_visible_button(event)

    toggle_slider(cell_slider, isVisible)

    toggle_cell_layer_visibility(isVisible)
    toggle_path_layer_visibility(isVisible)    

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
