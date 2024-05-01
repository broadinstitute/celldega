import { Deck, ScatterplotLayer } from 'deck.gl';
import { tile_cat } from "../global_variables/tile_cat.js"; 
import { tile_scatter_data } from "../global_variables/tile_scatter_data.js";

class SquareScatterplotLayer extends ScatterplotLayer {
    getShaders() {
        // Get the default shaders from the ScatterplotLayer
        const shaders = super.getShaders();

        // Redefine the fragment shader using template literals for multi-line text
        shaders.fs = `#version 300 es
        #define SHADER_NAME scatterplot-layer-fragment-shader
        precision highp float;
        in vec4 vFillColor;
        in vec2 unitPosition;
        out vec4 fragColor;
        void main(void) {
            geometry.uv = unitPosition;
            fragColor = vFillColor;
            DECKGL_FILTER_COLOR(fragColor, geometry);
        }`;

        return shaders;
    }
}    

export let square_scatter_layer

export const update_square_scatter_layer = ( tile_scatter_data, tile_cats_array, color_dict ) => {

    let inst_color

    square_scatter_layer = new SquareScatterplotLayer({
        id: 'tile-layer',
        data: tile_scatter_data,
        getFillColor: (i, d) => {

            if (tile_cat === 'cluster') {   
                var inst_name = tile_cats_array[d.index]
                inst_color = color_dict[inst_name]
            } else {
                inst_color = [0, 0, 255]
            }

            return [inst_color[0], inst_color[1], inst_color[2], 255]
        },
        filled: true,
        getRadius: 0.5, // 8um: 12 with border
        pickable: true,
        onClick: d => console.log('Clicked on:', d),
        updateTriggers: {
            getFillColor: [tile_cat]  // This line ensures getFillColor is recalculated when tile_cat changes
        }        
    })

}