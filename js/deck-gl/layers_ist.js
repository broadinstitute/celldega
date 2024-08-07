// Import the necessary layers and variables
import { background_layer } from './background_layer.js';
import { image_layers } from './image_layers.js';
import { path_layer } from './path_layer.js';
import { cell_layer } from './cell_layer.js';
import { trx_layer } from './trx_layer.js';
import { close_up } from '../global_variables/close_up.js';

// Initialize new_layers and layers_ist
let new_layers;
export let layers_ist = [];

// Function to update layers_ist based on the close_up variable
export const update_layers_ist = () => {

    console.log('--------------------')
    console.log('running origial update_layers_ist')
    console.log('background_layer', background_layer)
    console.log('image_layers', image_layers)
    console.log('path_layer', path_layer)
    console.log('cell_layer', cell_layer)
    console.log('trx_layer', trx_layer)
    console.log('--------------------')

    if (close_up) {
        new_layers = [
            background_layer,
            ...image_layers,
            path_layer,
            cell_layer,
            trx_layer
        ];
    } else {
        new_layers = [
            background_layer,
            ...image_layers,
            cell_layer,
        ];
    }

    layers_ist = new_layers;

    console.log(layers_ist)
};


export const get_layers_list = (layers_obj, close_up) => {

    let layers_list

    if (close_up) {
        layers_list = [
            layers_obj.background_layer,
            ...layers_obj.image_layers,
            layers_obj.path_layer,
            layers_obj.cell_layer,
            layers_obj.trx_layer
        ]
    } else {
        layers_list = [
            layers_obj.background_layer,
            ...layers_obj.image_layers,
            layers_obj.cell_layer,
        ]
    }

    return layers_list

}