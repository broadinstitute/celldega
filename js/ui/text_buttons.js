import * as d3 from 'd3';
import { simple_image_layer, simple_image_layer_visibility } from '../deck-gl/simple_image_layer';
import { square_scatter_layer, square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer';
import { layers_sst, update_layers_sst } from '../deck-gl/layers_sst';

import { image_layers, toggle_visibility_image_layers } from '../deck-gl/image_layers';
import { deck_sst } from '../deck-gl/deck_sst';
import { deck } from '../deck-gl/deck';

import { background_layer, toggle_background_layer_visibility } from '../deck-gl/background_layer';
import { path_layer } from '../deck-gl/path_layer';
import { cell_layer } from '../deck-gl/cell_layer';
import { trx_layer } from '../deck-gl/trx_layer';
import { layers, update_layers } from '../deck-gl/layers';

const make_button = (container, text, color, callback) => {
    
    d3.select(container)
        .append('div')
        .attr('class', 'button')
        .text(text)
        .style('width', '50px')
        .style('text-align', 'center')
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', color)
        .style('margin-top', '5px')
        .style('user-select', 'none')
        .on('click', callback);  
        
}

const sst_img_button_callback = async (event) => {

    const current = d3.select(event.currentTarget);

    let isVisible;
    if (current.style('color') === 'blue') {
        current.style('color', 'gray')
        isVisible = false
    } else {
        current.style('color', 'blue')
        isVisible = true
    }

    simple_image_layer_visibility(isVisible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst});

}


const ist_img_button_callback = async (event) => {

    const current = d3.select(event.currentTarget);

    let isVisible;
    if (current.style('color') === 'blue') {
        current.style('color', 'gray')
        isVisible = false
    } else {
        current.style('color', 'blue')
        isVisible = true
    }

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
    deck.setProps({layers});

}

const tile_button_callback = async (event) => {

    const current = d3.select(event.currentTarget);

    let isVisible;
    if (current.style('color') === 'blue') {
        current.style('color', 'gray')
        isVisible = false
    } else {
        current.style('color', 'blue')
        isVisible = true
    }

    square_scatter_layer_visibility(isVisible)
    await update_layers_sst([simple_image_layer, square_scatter_layer])
    deck_sst.setProps({layers: layers_sst});

}    

export const make_img_button = (container, type_st) => {
    if (type_st === 'sst') {
        make_button(container, 'IMG', 'blue', sst_img_button_callback)
    } else {
        make_button(container, 'IMG', 'blue', ist_img_button_callback)
    }
}

export const make_tile_button = (container) => {
    make_button(container, 'TILE', 'blue', tile_button_callback)
}