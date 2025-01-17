import { update_meta_cluster } from '../global_variables/meta_cluster'
import { update_cell_cats } from '../global_variables/cat'
import { update_cell_layer_id } from '../deck-gl/cell_layer'
import { get_layers_list } from '../deck-gl/layers_ist'
import { update_bar_graph } from '../ui/bar_plot'
import { bar_callback_cluster } from '../ui/bar_plot'

export const update_cell_clusters = (deck_ist, layers_obj, viz_state) => {

    const new_cluster_info = viz_state.model.get('cell_clusters')

    update_meta_cluster(viz_state.cats, new_cluster_info['meta_cluster'])
    update_cell_cats(viz_state.cats, new_cluster_info['new_clusters'])

    update_cell_layer_id(layers_obj, 'cluster')

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    viz_state.combo_data.cell = viz_state.combo_data.cell.map((cell) => ({
        ...cell,
        cat: viz_state.cats.dict_cell_cats[cell.name]
      }))

    update_bar_graph(
        viz_state.cats.svg_bar_cluster,
        viz_state.cats.cluster_counts,
        viz_state.cats.color_dict_cluster,
        bar_callback_cluster,
        [],
        deck_ist,
        layers_obj,
        viz_state
    )

}
