import { simple_image_layer } from "../deck-gl/simple_image_layer"
import { square_scatter_layer, square_scatter_layer_opacity } from "../deck-gl/square_scatter_layer"
import { layers_sst, update_layers_sst } from "../deck-gl/layers_sst"
import { trx_layer, update_trx_layer_radius } from "../deck-gl/trx_layer"
import { image_layers } from "../deck-gl/image_layers"
import { path_layer } from "../deck-gl/path_layer"
import { cell_layer, update_cell_layer_radius } from "../deck-gl/cell_layer"
import { deck_sst } from "../deck-gl/deck_sst"
import { deck_ist } from "../deck-gl/deck_ist"
import { background_layer } from "../deck-gl/background_layer"
import { trx_ini_raidus } from "../global_variables/trx_ini_raidus"

export let tile_slider = document.createElement("input")
export let cell_slider = document.createElement("input")
export let trx_slider = document.createElement("input")

export const ini_tile_slider = () => {
    
    tile_slider.type = "range";
    tile_slider.min = "0";
    tile_slider.max = "100";
    tile_slider.value = "100";
    tile_slider.className = "slider";

    tile_slider.addEventListener("input", async function() {
        square_scatter_layer_opacity(tile_slider.value / 100)
        await update_layers_sst([simple_image_layer, square_scatter_layer])
        deck_sst.setProps({layers: layers_sst})
    });        
    
}

export const ini_cell_slider = () => {

    cell_slider.type = "range"
    cell_slider.min = "0"
    cell_slider.max = "100"
    cell_slider.value = trx_ini_raidus * 100
    cell_slider.className = "slider"

    cell_slider.addEventListener("input", async function() {

        update_cell_layer_radius(cell_slider.value/10)

        let new_layers = [
            background_layer,
            ...image_layers, 
            path_layer, 
            cell_layer, 
            trx_layer
        ]
        
        deck_ist.setProps({layers: new_layers})
    });        
          
}

export const ini_trx_slider = () => {

    trx_slider.type = "range"
    trx_slider.min = "0"
    trx_slider.max = "100"
    trx_slider.value = trx_ini_raidus * 100
    trx_slider.className = "slider"

    trx_slider.addEventListener("input", async function() {
        update_trx_layer_radius(trx_slider.value/100)
        let new_layers = [
            background_layer,
            ...image_layers, 
            path_layer, 
            cell_layer, 
            trx_layer
        ]
        
        deck_ist.setProps({layers: new_layers})
    });        
    
}

export const toggle_slider = (slider, state) => {
    slider.disabled = !state
}