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

export const initUpdateLayers = () => {
    // Function to update layers_ist based on the close_up variable
    const update_layers_ist = () => {
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
    };

    return update_layers_ist;
};

// Initialize the update_layers_ist function and export it
export const update_layers_ist = initUpdateLayers();
