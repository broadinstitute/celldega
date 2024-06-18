import * as d3 from 'd3';
import { simple_image_layer, simple_image_layer_visibility } from '../deck-gl/simple_image_layer';
import { square_scatter_layer, square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer';
import { layers, update_layers } from '../deck-gl/layers_sst';
import { deck } from '../deck-gl/deck_sst';

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
    await update_layers([simple_image_layer, square_scatter_layer])
    deck.setProps({layers});

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

    console.log('toggle ist image layer visibility')

    // simple_image_layer_visibility(isVisible)
    // await update_layers([simple_image_layer, square_scatter_layer])
    // deck.setProps({layers});

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
    await update_layers([simple_image_layer, square_scatter_layer])
    deck.setProps({layers});

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