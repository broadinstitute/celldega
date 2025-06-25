import { ScatterplotLayer } from 'deck.gl';

import { update_cat, update_selected_cats } from '../../global_variables/cat';
import { update_cell_exp_array } from '../../global_variables/cell_exp_array';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { grab_trx_tiles_in_view } from '../../vector_tile/transcripts/grab_trx_tiles_in_view';
import { get_layers_list } from '../utils/layers_ist';

const trx_layer_callback = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_gene = viz_state.genes.trx_names_array[info.index];

  if (!inst_gene) {
    // console.error("Invalid gene name at index:", info.index)
    return;
  }

  const reset_gene = inst_gene === viz_state.cats.cat;

  const new_cat = reset_gene ? 'cluster' : inst_gene;

  update_cat(viz_state.cats, new_cat);

  update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
  // testing setting selected_cats to array with the selected gene for
  // observable updates
  update_selected_cats(viz_state.cats, [inst_gene], viz_state.obs_store);

  await update_cell_exp_array(
    viz_state.cats,
    viz_state.genes,
    viz_state.global_base_url,
    inst_gene,
    viz_state.seg.version,
    viz_state.vector_name_integer,
    viz_state.aws
  );

  const layers_list = get_layers_list(layers_obj, viz_state.close_up);
  deck_ist.setProps({ layers: layers_list });

};

export const ini_trx_layer = (genes) => {
  const trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: genes.trx_data,
    pickable: true,
    getFillColor: (i, d) => {
      const inst_gene = genes.trx_names_array[d.index];
      const inst_color = genes.color_dict_gene[inst_gene];
      const inst_opacity =
        genes.selected_genes.length === 0 ||
        genes.selected_genes.includes(inst_gene)
          ? 255
          : 5;

      return [...inst_color, inst_opacity];
    },
  });

  return trx_layer;
};

export const set_trx_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    onClick: (event, d) =>
      trx_layer_callback(event, d, deck_ist, layers_obj, viz_state),
  });
};

export const update_trx_layer_data = async (
  base_url,
  tiles_in_view,
  layers_obj,
  viz_state
) => {
  viz_state.genes.trx_data = await grab_trx_tiles_in_view(
    base_url,
    tiles_in_view,
    viz_state
  );

  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    data: viz_state.genes.trx_data,
  });
};

export const toggle_trx_layer_visibility = (layers_obj, visible) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    visible,
  });
};

export const update_trx_layer_radius = (layers_obj, radius) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    getRadius: radius,
  });
};

export const update_trx_pickable_state = (layers_obj, pickable) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    pickable,
  });
};
