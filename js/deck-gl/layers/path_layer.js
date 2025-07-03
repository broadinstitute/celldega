import { PathLayer } from 'deck.gl';

import { update_selected_cats, update_cat } from '../../global_variables/cat';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { grab_cell_tiles_in_view } from '../../vector_tile/polygons/grab_cell_tiles_in_view';
import { get_layers_list } from '../utils/layers_ist';

export const get_path_color = (cats, i, d) => {
  const inst_cell_id = cats.polygon_cell_names[d.index];
  const inst_cat = cats.dict_cell_cats[inst_cell_id];

  let inst_color;

  // check if inst_cat is not in cats.color_dict_cluster
  if (inst_cat in cats.color_dict_cluster) {
    inst_color = cats.color_dict_cluster[inst_cat];
  } else {
    // default segmentation color
    inst_color = [0, 0, 255];
  }

  const inst_opacity =
    cats.selected_cats.length === 0 || cats.selected_cats.includes(inst_cat)
      ? 255
      : 50;

  return [...inst_color, inst_opacity];
};

export const ini_path_layer = (viz_state) => {
  const path_layer = new PathLayer({
    id: 'path-layer',
    data: [],
    pickable: true,
    widthScale: 3,
    widthMinPixels: 1,
    getPath: (d) => d,
    getColor: (i, d) => get_path_color(viz_state.cats, i, d),
    widthUnits: 'pixels',
  });

  return path_layer;
};

const path_layer_onclick = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_cell_id = viz_state.cats.polygon_cell_names[info.index];
  const inst_cat = viz_state.cats.dict_cell_cats[inst_cell_id];

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });

  update_cat(viz_state.cats, 'cluster');
  update_selected_cats(viz_state.cats, [inst_cat], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);
};

export const update_path_layer_data = async (
  base_url,
  tiles_in_view,
  layers_obj,
  viz_state
) => {
  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    path_layer: false,
  });
  const polygonPathsConcat = await grab_cell_tiles_in_view(
    base_url,
    tiles_in_view,
    viz_state
  );

  layers_obj.path_layer = layers_obj.path_layer.clone({
    data: polygonPathsConcat,
  });

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    path_layer: true,
  });
};

export const set_path_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.path_layer = layers_obj.path_layer.clone({
    onClick: (info, d) =>
      path_layer_onclick(info, d, deck_ist, layers_obj, viz_state),
  });
};

export const toggle_path_layer_visibility = (layers_obj, visible) => {
  layers_obj.path_layer = layers_obj.path_layer.clone({
    visible,
  });
};

export const update_path_pickable_state = (layers_obj, pickable) => {
  layers_obj.path_layer = layers_obj.path_layer.clone({
    pickable,
  });
};
