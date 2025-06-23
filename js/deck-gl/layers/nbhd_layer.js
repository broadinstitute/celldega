// /* eslint-disable import/no-cycle */

import { GeoJsonLayer } from 'deck.gl';

import { update_selected_cats, update_cat } from '../../global_variables/cat';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { hexToRgb } from '../../utils/hexToRgb';
import { get_layers_list } from '../utils/layers_ist';

import { update_cell_layer_id } from './cell_layer';
import { update_path_layer_id } from './path_layer';

export const ini_nbhd_layer = (viz_state, visible) => {
  // console.log(viz_state.nbhd.feature_collection)

  const nbhd_layer = new GeoJsonLayer({
    id: 'nbhd-layer',
    data: viz_state.nbhd.feature_collection,
    pickable: true,
    stroked: false,
    filled: true,
    getLineWidth: 1,
    getFillColor: (d) => hexToRgb(d.properties.color),
    opacity: 0.5,
    visible,
  });

  return nbhd_layer;
};

export const filter_cat_nbhd_feature_collection = (viz_state) => {
  let filt_features;

  if (viz_state.cats.selected_cats.length === 0) {
    filt_features = viz_state.nbhd.ini_feature_collection.features.filter(
      (d) => d.properties.inv_alpha === viz_state.nbhd.inst_alpha
    );
  } else {
    filt_features = viz_state.nbhd.ini_feature_collection.features
      .filter((d) => viz_state.cats.selected_cats.includes(d.properties.cat))
      .filter((d) => d.properties.inv_alpha === viz_state.nbhd.inst_alpha);
  }
  viz_state.nbhd.feature_collection = {
    type: 'FeatureCollection',
    features: filt_features,
  };
};

export const update_nbhd_layer_data = (viz_state, layers_obj) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    data: viz_state.nbhd.feature_collection,
  });
};

const nbhd_layer_onclick = async (
  info,
  _event,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_cat = info.object.properties.cat;

  update_cat(viz_state.cats, 'cluster');
  update_selected_cats(viz_state.cats, [inst_cat], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);

  const inst_cat_name = viz_state.cats.selected_cats.join('-');

  update_cell_layer_id(layers_obj, inst_cat_name);
  update_path_layer_id(layers_obj, inst_cat_name);

  // update data for nbhd layer

  await filter_cat_nbhd_feature_collection(viz_state);
  await update_nbhd_layer_data(viz_state, layers_obj);

  const layers_list = get_layers_list(layers_obj, viz_state.close_up);
  deck_ist.setProps({ layers: layers_list });

};

export const set_nbhd_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    onClick: (info, event) =>
      nbhd_layer_onclick(info, event, deck_ist, layers_obj, viz_state),
  });
};

export const toggle_nbhd_layer_visibility = (layers_obj, visible) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    visible,
  });
};
