import { update_cell_layer_id } from '../deck-gl/layers/cell_layer';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import { update_cell_cats } from '../global_variables/cat';
import { update_meta_cluster } from '../global_variables/meta_cluster';
import { update_bar_graph, bar_callback_cluster } from '../ui/bar_plot';

export const update_cell_clusters = (deck_ist, layers_obj, viz_state) => {
  console.log('update_cell_clusters called');
  const new_cluster_info = viz_state.model.get('cell_clusters');

  update_meta_cluster(viz_state.cats, new_cluster_info['meta_cluster']);
  update_cell_cats(viz_state.cats, new_cluster_info['new_clusters']);

  update_cell_layer_id(layers_obj, 'cluster');

  const layers_list = get_layers_list(layers_obj, viz_state.close_up);
  deck_ist.setProps({ layers: layers_list });

  viz_state.combo_data.cell = viz_state.combo_data.cell.map((cell) => ({
    ...cell,
    cat: viz_state.cats.dict_cell_cats[cell.name],
  }));

  // update to bar graph should take place via observable

};
