import { PathLayer } from 'deck.gl';
import { grab_cell_tiles_in_view } from '../vector_tile/polygons/grab_cell_tiles_in_view';

export let path_layer = new PathLayer({
        id: 'path_layer',
        data: [],
        pickable: true,
        widthScale: 3,
        widthMinPixels: 1,
        getPath: d => d,
        getColor: [0, 0, 255, 150], // white outline
        widthUnits: 'pixels',
    })

export const update_path_layer = async (base_url, tiles_in_view) => {

    const polygonPathsConcat = grab_cell_tiles_in_view(base_url, tiles_in_view)

    path_layer = new PathLayer({
        // Re-use existing layer props
        ...path_layer.props,
        data: polygonPathsConcat,
    });

}

export const toggle_path_layer_visibility = (visible) => {
    path_layer = path_layer.clone({
        visible: visible,
    });
}