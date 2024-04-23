import { PathLayer } from 'deck.gl';
import { grab_cell_tiles_in_view } from '../vector_tile/polygons/grab_cell_tiles_in_view';

export const make_polygon_layer_new = async (
    tiles_in_view, 
    options, 
    base_url,
    polygon_layer
) => {

    const polygonPathsConcat = grab_cell_tiles_in_view(base_url, tiles_in_view, options)

    const polygon_layer_new = new PathLayer({
        // Re-use existing layer props
        ...polygon_layer.props,
        data: polygonPathsConcat,
    });

    return polygon_layer_new

}