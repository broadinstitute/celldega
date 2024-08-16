 /* eslint-disable */
import { ScatterplotLayer } from 'deck.gl';
import { cat, update_cat } from "../global_variables/cat.js";
import { tile_scatter_data } from "../global_variables/tile_scatter_data.js";
import { tile_cats_array } from "../global_variables/tile_cats_array.js";
import {tile_color_dict } from '../global_variables/tile_color_dict.js';
import { tile_exp_array } from '../global_variables/tile_exp_array.js';
// import { selected_cats, update_selected_cats } from '../global_variables/cat'
import { deck_sst } from "./deck_sst.js";
import { simple_image_layer } from "../deck-gl/simple_image_layer.js";

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

const square_scatter_layer_color = (i, d) => {
    if (cat === 'cluster') {
        const inst_cat = tile_cats_array[d.index];
        // const opacity = (selected_cats.length === 0 || selected_cats.includes(inst_cat)) ? 255 : 25;
        // return [...tile_color_dict[inst_cat], opacity];
    } else {
        const inst_exp = tile_exp_array[d.index];
        return [255, 0, 0, inst_exp];
    }
}


export const ini_square_scatter_layer = () => {

    square_scatter_layer = new SquareScatterplotLayer({
        id: 'tile-layer',
        data: tile_scatter_data,
        getFillColor: square_scatter_layer_color,
        filled: true,
        getRadius: 3, // 8um: 12 with border
        pickable: true,
        onClick: (d) => {
            // let new_selected_cats = [tile_cats_array[d.index]]

            // update_selected_cats(new_selected_cats)
            // update_cat('cluster')
            // update_square_scatter_layer()
            // deck_sst.setProps({layers: [simple_image_layer, square_scatter_layer]})

        },
        updateTriggers: {
            getFillColor: [cat]
        }
    })

}

export const update_square_scatter_layer = () => {
    // // Determine the new layer ID based on the selected categories
    // const layer_id = selected_cats.length === 0
    //     ? `tile-layer-${cat}`
    //     : `tile-layer-${cat}-${selected_cats.join('-')}`;

    // // Clone the existing layer and update the ID and data
    // square_scatter_layer = square_scatter_layer.clone({
    //     id: layer_id,
    //     data: tile_scatter_data,
    // });
}


export const square_scatter_layer_visibility = (visible) => {

    square_scatter_layer = square_scatter_layer.clone({
        visible: visible,
    });

}

export const square_scatter_layer_opacity = (opacity) => {

    square_scatter_layer = square_scatter_layer.clone({
        opacity: opacity
    });

}

