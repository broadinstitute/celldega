 /* eslint-disable */
import { ScatterplotLayer } from 'deck.gl';
import { update_cat, update_selected_cats } from "../global_variables/cat.js";
import { deck_sst } from "./deck_sst.js";

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

const square_scatter_layer_color = (i, d, cats) => {

    let tile_color_dict = cats.tile_color_dict

    if (cats.cat === 'cluster') {
        const inst_cat = cats.tile_cats_array[d.index];
        const opacity = (cats.selected_cats.length === 0 || cats.selected_cats.includes(inst_cat)) ? 255 : 5;
        return [...tile_color_dict[inst_cat], opacity];
    } else {
        const inst_exp = cats.tile_exp_array[d.index];
        return [255, 0, 0, inst_exp];
    }
}


export const ini_square_scatter_layer = (cats) => {

    let square_scatter_layer = new SquareScatterplotLayer({
        id: 'tile-layer',
        data: cats.tile_scatter_data,
        getFillColor: (i, d) => square_scatter_layer_color(i, d, cats),
        filled: true,
        // getRadius: 3, // 8um: 12 with border
        getRadius: cats.square_tile_size, // 8um: 12 with border
        pickable: true,
        updateTriggers: {
            getFillColor: [cats.cat]
        }
    })

    return square_scatter_layer

}

export const update_square_scatter_layer = (viz_state, layers_sst) => {

    // Determine the new layer ID based on the selected categories
    const layer_id = viz_state.cats.selected_cats.length === 0
        ? `tile-layer-${viz_state.cats.cat}`
        : `tile-layer-${viz_state.cats.cat}-${viz_state.cats.selected_cats.join('-')}`;

    // Clone the existing layer and update the ID and data
    layers_sst.square_scatter_layer = layers_sst.square_scatter_layer.clone({
        id: layer_id,
        data: viz_state.cats.tile_scatter_data,
    });
}


export const square_scatter_layer_visibility = (layser_sst, visible) => {

    layser_sst.square_scatter_layer = layser_sst.square_scatter_layer.clone({
        visible: visible,
    });

}

export const square_scatter_layer_opacity = (layers_sst, opacity) => {

    layers_sst.square_scatter_layer = layers_sst.square_scatter_layer.clone({
        opacity: opacity
    });

}

export const set_tile_layer_onclick = (deck_sst, layers_sst, viz_state) => {

    layers_sst.square_scatter_layer = layers_sst.square_scatter_layer.clone({
        onClick: (event, d) => tile_layer_onclick(event, d, deck_sst, layers_sst, viz_state)
    })

    deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})

}

const tile_layer_onclick = (event, d, deck_sst, layers_sst, viz_state) => {

    // Check if the device is a touch device
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    let inst_cat;

    if (isTouchDevice) {
        // Fallback on the previous method for touch devices
        inst_cat = viz_state.cats.tile_cats_array[event.index]
    } else {
        // Use the tooltip category for non-touch devices
        inst_cat = viz_state.tooltip_cat_cell;
    }

    let new_selected_cats = [inst_cat]

    update_selected_cats(viz_state.cats, new_selected_cats)
    update_cat(viz_state.cats, 'cluster')

    update_square_scatter_layer(viz_state, layers_sst)
    deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})
}