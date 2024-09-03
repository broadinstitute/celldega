import * as mathGl from 'math.gl';
import { CustomBitmapLayer } from './CustomBitmapLayer';

export const create_render_tile_sublayers = (viz_state, color, opacity) => (props) => {

    const {
        bbox: {left, bottom, right, top}
    } = props.tile;
    const {width, height} = viz_state.dimensions;

    return new CustomBitmapLayer(props, {
        data: null,
        image: props.data,
        bounds: [
            mathGl.clamp(left, 0, width),
            mathGl.clamp(bottom, 0, height),
            mathGl.clamp(right, 0, width),
            mathGl.clamp(top, 0, height)
        ],
        color: color,
        opacityScale: opacity,
    });

}