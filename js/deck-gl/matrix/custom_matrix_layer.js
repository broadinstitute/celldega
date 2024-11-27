import { ScatterplotLayer } from 'deck.gl';
import { vs, fs } from './mat_shaders.js'

export class CustomMatrixLayer extends ScatterplotLayer {

    getShaders() {

        const shaders = super.getShaders();
        shaders.vs = vs
        shaders.fs = fs

        return shaders;
    }

    // Add custom uniforms
    draw({ uniforms }) {
        super.draw({
        uniforms: {
            ...uniforms,
            tile_height: this.props.tile_height,
            tile_width: this.props.tile_width,
        }
        });
    }

}