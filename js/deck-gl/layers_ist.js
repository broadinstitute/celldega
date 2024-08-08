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