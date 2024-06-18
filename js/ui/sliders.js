import { simple_image_layer } from "../deck-gl/simple_image_layer";
import { square_scatter_layer, square_scatter_layer_opacity } from "../deck-gl/square_scatter_layer";
import { layers, update_layers } from "../deck-gl/layers_sst";
import { deck } from "../deck-gl/deck_sst";

export const make_tile_slider = (container) => {
    let tile_slider = document.createElement("input");
    tile_slider.type = "range";
    tile_slider.min = "0";
    tile_slider.max = "100";
    tile_slider.value = "100";
    tile_slider.className = "slider";

    tile_slider.addEventListener("input", async function() {
        square_scatter_layer_opacity(tile_slider.value / 100)
        await update_layers([simple_image_layer, square_scatter_layer])
        deck.setProps({layers});        
    });        
    
    container.appendChild(tile_slider);            
}