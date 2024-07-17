import { PathLayer } from 'deck.gl';
import { grab_cell_tiles_in_view } from '../vector_tile/polygons/grab_cell_tiles_in_view';
import { polygon_cell_names } from '../vector_tile/polygons/grab_cell_tiles_in_view';
import { dict_cell_cats } from '../global_variables/cat';
import { cell_color_dict } from '../global_variables/cell_color_dict';

export const get_path_color = (i, d) => {

    const inst_cell_id = polygon_cell_names[d.index]

    const inst_cat = dict_cell_cats[inst_cell_id]

    let inst_color = cell_color_dict[inst_cat]
    const inst_opacity = 255

    // Check if inst_color is an array and log an error if it's not
    if (!Array.isArray(inst_color)) {
        inst_color = [0, 0, 0]
    }

    return [...inst_color, inst_opacity]

}

export let path_layer = new PathLayer({
        id: 'path-layer',
        data: [],
        pickable: true,
        widthScale: 3,
        widthMinPixels: 1,
        getPath: d => d,
        getColor: get_path_color, // white outline
        widthUnits: 'pixels',
    })

export const update_path_layer = async (base_url, tiles_in_view) => {

    const polygonPathsConcat = await grab_cell_tiles_in_view(base_url, tiles_in_view)

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