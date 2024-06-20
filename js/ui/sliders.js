import { simple_image_layer } from "../deck-gl/simple_image_layer";
import { square_scatter_layer, square_scatter_layer_opacity } from "../deck-gl/square_scatter_layer";
import { layers_sst, update_layers_sst } from "../deck-gl/layers_sst";
import { deck_sst } from "../deck-gl/deck_sst";

export const make_tile_slider = (container) => {
    let tile_slider = document.createElement("input");
    tile_slider.type = "range";
    tile_slider.min = "0";
    tile_slider.max = "100";
    tile_slider.value = "100";
    tile_slider.className = "slider";

    tile_slider.addEventListener("input", async function() {
        console.log('here!!')
        square_scatter_layer_opacity(tile_slider.value / 100)
        await update_layers_sst([simple_image_layer, square_scatter_layer])
        deck_sst.setProps({layers: layers_sst})
    });        
    
    container.appendChild(tile_slider);            
}