import { PathLayer } from 'deck.gl'
import { grab_cell_tiles_in_view } from '../vector_tile/polygons/grab_cell_tiles_in_view'
import { update_selected_cats, update_cat } from '../global_variables/cat'
import { update_cell_layer_id } from './cell_layer'
import { get_layers_list } from './layers_ist'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { update_selected_genes } from '../global_variables/selected_genes'
import { update_trx_layer_id } from './trx_layer'

export const get_path_color = (cats, i, d) => {

    const inst_cell_id = cats.polygon_cell_names[d.index]
    const inst_cat = cats.dict_cell_cats[inst_cell_id]

    let inst_color

    // check if inst_cat is not in cats.color_dict_cluster
    if (inst_cat in cats.color_dict_cluster) {
        inst_color = cats.color_dict_cluster[inst_cat]
    } else {
        // default segmentation color
        inst_color = [0, 0, 255]
    }

    const inst_opacity = cats.selected_cats.length === 0 || cats.selected_cats.includes(inst_cat) ? 255 : 50

    return [...inst_color, inst_opacity]

}

export const ini_path_layer = (viz_state) => {

    let path_layer = new PathLayer({
        id: 'path-layer',
        data: [],
        pickable: true,
        widthScale: 3,
        widthMinPixels: 1,
        getPath: d => d,
        getColor: (i, d) => get_path_color(viz_state.cats, i, d),
        widthUnits: 'pixels',
    })

    return path_layer

}

const path_layer_onclick = (info, d, deck_ist, layers_obj, viz_state) => {

    const inst_cell_id = viz_state.cats.polygon_cell_names[info.index]
    const inst_cat = viz_state.cats.dict_cell_cats[inst_cell_id]

    update_cat(viz_state.cats, 'cluster')
    update_selected_cats(viz_state.cats, [inst_cat])
    update_selected_genes(viz_state.genes, [])

    toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

    const inst_cat_name = viz_state.cats.selected_cats.join('-')

    update_cell_layer_id(layers_obj, inst_cat_name)
    update_path_layer_id(layers_obj, inst_cat_name)
    update_trx_layer_id(viz_state.genes, layers_obj)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}


export const update_path_layer_data = async (base_url, tiles_in_view, layers_obj, viz_state) => {

    const polygonPathsConcat = await grab_cell_tiles_in_view(base_url, tiles_in_view, viz_state)

    layers_obj.path_layer = layers_obj.path_layer.clone({
        data: polygonPathsConcat,
    })

}

export const set_path_layer_onclick = (deck_ist, layers_obj, viz_state) => {
    layers_obj.path_layer = layers_obj.path_layer.clone({
        onClick: (info, d) => path_layer_onclick(info, d, deck_ist, layers_obj, viz_state),
    })
}

export const toggle_path_layer_visibility = (layers_obj, visible) => {
    layers_obj.path_layer = layers_obj.path_layer.clone({
        visible: visible,
    });
}

export const update_path_layer_id = (layers_obj, new_cat) => {
    layers_obj.path_layer = layers_obj.path_layer.clone({
        id: 'path-layer-' + new_cat,
    });
}

export const update_path_pickable_state = (layers_obj, pickable) => {
    layers_obj.path_layer = layers_obj.path_layer.clone({
        pickable: pickable,
    });
}