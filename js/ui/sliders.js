import { simple_image_layer } from "../deck-gl/simple_image_layer"
import { square_scatter_layer, square_scatter_layer_opacity } from "../deck-gl/square_scatter_layer"
import { layers_sst, update_layers_sst } from "../deck-gl/layers_sst"
import { trx_layer, update_trx_layer_radius } from "../deck-gl/trx_layer"
import { image_layers } from "../deck-gl/image_layers"
import { path_layer } from "../deck-gl/path_layer"
import { cell_layer } from "../deck-gl/cell_layer"
import { deck_sst } from "../deck-gl/deck_sst"
import { deck_ist } from "../deck-gl/deck_ist"
import { background_layer } from "../deck-gl/background_layer"

export const make_tile_slider = (container) => {
    let tile_slider = document.createElement("input");
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
    
    container.appendChild(tile_slider);            
}

export const make_trx_slider = (container) => {
    let trx_slider = document.createElement("input");
    trx_slider.type = "range";
    trx_slider.min = "0";
    trx_slider.max = "100";
    trx_slider.value = "100";
    trx_slider.className = "slider";

    trx_slider.addEventListener("input", async function() {
        console.log('trx_slider')
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
    
    container.appendChild(trx_slider);            
}