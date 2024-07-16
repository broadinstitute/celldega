import { background_layer } from './background_layer.js'
import { image_layers } from './image_layers.js'
import { path_layer } from './path_layer.js'
import { cell_layer } from './cell_layer.js'
import { trx_layer } from './trx_layer.js'
import { close_up } from '../global_variables/close_up.js'

let new_layers

export let layers_ist = []

export const update_layers_ist = () => {

    if (close_up){
        new_layers = [
            background_layer,
            ...image_layers,
            path_layer,
            cell_layer,
            trx_layer
        ]
    } else {
        new_layers = [
            background_layer,
            ...image_layers,
            cell_layer,
        ]
    }
    layers_ist = new_layers
}


