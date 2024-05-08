import { ScatterplotLayer } from 'deck.gl';
import { tile_cat } from "../global_variables/tile_cat.js"; 
import { tile_scatter_data } from "../global_variables/tile_scatter_data.js";
import { tile_cats_array } from "../global_variables/tile_cats_array.js";
import { color_dict } from '../global_variables/tile_color_dict.js';
import { tile_exp_array } from '../global_variables/tile_exp_array.js'; 
import { selected_cats, update_selected_cats } from '../global_variables/selected_cats.js';
import { update_tile_cat } from "../global_variables/tile_cat.js" 
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"; 
import { deck } from "../deck-gl/toy_deck.js";

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

export const ini_square_scatter_layer = (base_url) => {

    square_scatter_layer = new SquareScatterplotLayer({
        id: 'tile-layer',
        data: tile_scatter_data,
        getFillColor: (i, d) => {

            let inst_color

            if (tile_cat === 'cluster') {   
                var inst_cat = tile_cats_array[d.index]

                if (selected_cats.length === 0){
                    inst_color = [...color_dict[inst_cat], 255]
                } else {
                    if (selected_cats.includes(inst_cat)) {
                        inst_color = [...color_dict[inst_cat], 255]
                    } else {
                        inst_color = [0, 0, 0, 20]
                    
                    }
                }
            } else {
                let inst_exp = tile_exp_array[d.index]
                inst_color = [255, 0, 0, inst_exp]
            }

            return inst_color
        },
        filled: true,
        getRadius: 12.2, // 8um: 12 with border
        pickable: true,
        onClick: async (d) => {
            console.log('Clicked on:', d)
            let new_selected_cats = [tile_cats_array[d.index]]

            console.log('selected_cats', selected_cats)

            update_selected_cats(new_selected_cats)
            update_tile_cat('cluster')
            // await update_tile_exp_array(base_url, selected_gene)
            update_square_scatter_layer()
            deck.setProps({layers: [square_scatter_layer]})        

        },
        updateTriggers: {
            getFillColor: [tile_cat]  
        }        
    })

}

export const update_square_scatter_layer = () => {

    square_scatter_layer = new SquareScatterplotLayer({
        // Re-use existing layer props
        ...square_scatter_layer.props,
        id: `tile-layer-${tile_cat}`,
        data: tile_scatter_data,
    });

}