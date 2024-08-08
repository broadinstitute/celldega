import { PathLayer } from 'deck.gl'
import { grab_cell_tiles_in_view } from '../vector_tile/polygons/grab_cell_tiles_in_view'
import { polygon_cell_names } from '../vector_tile/polygons/grab_cell_tiles_in_view'
import { dict_cell_cats, update_selected_cats, selected_cats, update_cat } from '../global_variables/cat'
import { color_dict_cluster } from '../global_variables/meta_cluster'
import { new_update_cell_layer_id } from './cell_layer'
import { get_layers_list } from './layers_ist'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { update_selected_genes } from '../global_variables/selected_genes'
import { new_update_trx_layer_id } from './trx_layer'
import { close_up } from '../global_variables/close_up'

export const get_path_color = (i, d) => {

    const inst_cell_id = polygon_cell_names[d.index]
    const inst_cat = dict_cell_cats[inst_cell_id]

    let inst_color = color_dict_cluster[inst_cat]

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

export const ini_path_layer = () => {
    let path_layer = new PathLayer({
        id: 'path-layer',
        data: [],
        pickable: true,
        widthScale: 3,
        widthMinPixels: 1,
        getPath: d => d,
        getColor: get_path_color, // white outline
        widthUnits: 'pixels',
    })
    return path_layer
}

const path_layer_onclick = (info, d, deck_ist, layers_obj) => {

    const inst_cell_id = polygon_cell_names[info.index]
    const inst_cat = dict_cell_cats[inst_cell_id]

    update_cat('cluster')
    update_selected_cats([inst_cat])
    update_selected_genes

    toggle_image_layers_and_ctrls(!selected_cats.length > 0)

    const inst_cat_name = selected_cats.join('-')

    new_update_cell_layer_id(layers_obj, inst_cat_name)
    new_update_path_layer_id(layers_obj, inst_cat_name)
    new_update_trx_layer_id(layers_obj)

    const layers_list = get_layers_list(layers_obj, close_up)
    deck_ist.setProps({layers: layers_list})

}


export const update_path_layer_data = async (base_url, tiles_in_view, layers_obj) => {

    const polygonPathsConcat = await grab_cell_tiles_in_view(base_url, tiles_in_view)

    layers_obj.path_layer = layers_obj.path_layer.clone({
        data: polygonPathsConcat,
    })

}

export const set_path_layer_onclick = (deck_ist, layers_obj) => {
    layers_obj.path_layer = layers_obj.path_layer.clone({
        onClick: (info, d) => path_layer_onclick(info, d, deck_ist, layers_obj),
    })
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

export const new_update_path_layer_id = (layers_obj, new_cat) => {
    layers_obj.path_layer = layers_obj.path_layer.clone({
        id: 'path-layer-' + new_cat,
    });
}