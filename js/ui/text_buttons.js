import * as d3 from 'd3';
import { img_container, tile_container } from "./ui_containers";
import { simple_image_layer, simple_image_layer_visibility } from '../deck-gl/simple_image_layer';
import { square_scatter_layer, square_scatter_layer_visibility } from '../deck-gl/square_scatter_layer';
import { layers, update_layers } from '../deck-gl/layers_sst';
import { deck } from '../deck-gl/deck_sst';

export const make_img_button = () => {

    d3.select(img_container)
        .append('div')
        .attr('class', 'button blue')
        .text('IMG')
        .style('width', '50px')
        .style('text-align', 'center')        
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', 'blue')
        .style('margin-top', '5px')
        .style('user-select', 'none')
        .on('click', async (event) => {

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

        }); 
}

export const make_tile_button = () => {

    d3.select(tile_container)
        .append('div')
        .attr('class', 'button blue')
        .text('TILE')
        .style('width', '50px')
        .style('text-align', 'center')
        .style('cursor', 'pointer')
        .style('font-size', '16px')
        .style('font-weight', 'bold')
        .style('color', 'blue')
        .style('margin-top', '5px')
        .style('user-select', 'none')
        .on('click', async (event) => {

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

        });  
}