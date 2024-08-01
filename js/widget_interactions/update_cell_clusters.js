import { model } from '../global_variables/model'
import { update_meta_cluster } from '../global_variables/meta_cluster'
import { update_cell_cats } from '../global_variables/cat'
import { update_cell_layer_id, update_cell_combo_data } from '../deck-gl/cell_layer'
import { layers_ist, update_layers_ist } from '../deck-gl/layers_ist'
import { deck_ist } from '../deck-gl/deck_ist'
import { update_bar_graph } from '../ui/bar_plot'
import { svg_bar_cluster, bar_callback_cluster } from '../ui/bar_plot'
import { color_dict_cluster, cluster_counts } from '../global_variables/meta_cluster'

export const update_cell_clusters = () => {

    const new_cluster_info = model.get('cell_clusters')

    update_meta_cluster(new_cluster_info['meta_cluster'])
    update_cell_cats(new_cluster_info['new_clusters'])

    update_cell_layer_id('cluster')
    update_layers_ist()

    deck_ist.setProps({
        layers: layers_ist
    })

    update_cell_combo_data()

    update_bar_graph(
        svg_bar_cluster,
        cluster_counts,
        color_dict_cluster,
        bar_callback_cluster,
        []
    )

}
