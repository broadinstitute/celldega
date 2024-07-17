import { PathLayer } from 'deck.gl'
import { grab_cell_tiles_in_view } from '../vector_tile/polygons/grab_cell_tiles_in_view'
import { polygon_cell_names } from '../vector_tile/polygons/grab_cell_tiles_in_view'
import { dict_cell_cats, update_selected_cats, selected_cats } from '../global_variables/cat'
import { cell_color_dict } from '../global_variables/cell_color_dict'
import { update_cell_layer_id } from './cell_layer'
import { layers_ist, update_layers_ist } from './layers_ist'
import { deck_ist } from './deck_ist'

export const get_path_color = (i, d) => {

    const inst_cell_id = polygon_cell_names[d.index]
    const inst_cat = dict_cell_cats[inst_cell_id]

    let inst_color = cell_color_dict[inst_cat]

    // Check if inst_color is an array and log an error if it's not
    if (!Array.isArray(inst_color)) {
        inst_color = [0, 0, 0]
    }

    // if selected_cats is empty all cells are visible
    const inst_opacity = selected_cats.length === 0 || selected_cats.includes(inst_cat) ? 255 : 50

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

const path_layer_onclick = info => {

        const inst_cell_id = polygon_cell_names[info.index]
        const inst_cat = dict_cell_cats[inst_cell_id]

        update_selected_cats([inst_cat])

        const inst_cat_name = selected_cats.join('-')

        console.log('inst_cat_name', inst_cat_name)

        update_cell_layer_id(inst_cat_name)
        update_path_layer_id(inst_cat_name)
        update_layers_ist()

        deck_ist.setProps({layers: layers_ist})

}

export const update_path_layer = async (base_url, tiles_in_view) => {

    const polygonPathsConcat = await grab_cell_tiles_in_view(base_url, tiles_in_view)

    path_layer = new PathLayer({
        // Re-use existing layer props
        ...path_layer.props,
        data: polygonPathsConcat,
        onClick: path_layer_onclick,
    });

}

export const toggle_path_layer_visibility = (visible) => {
    path_layer = path_layer.clone({
        visible: visible,
    });
}

export const update_path_layer_id = (new_cat) => {
    path_layer = path_layer.clone({
        id: 'path-layer-' + new_cat,
    });
}