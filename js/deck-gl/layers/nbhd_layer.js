import { GeoJsonLayer } from 'deck.gl';

import { update_selected_cats, update_cat } from '../../global_variables/cat';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { hexToRgb } from '../../utils/hexToRgb';
import { get_layers_list } from '../utils/layers_ist';
import { refresh_layer } from '../../utils/refresh_layer';

const get_nbhd_color = (d, viz_state) => {

  let inst_color = hexToRgb(d.properties.color)

  let inst_opacity;

  // if viz_state.obs_store.selected_nbhds is not empty
  // then check if the cat is in the selected_nbhds
  if (viz_state.obs_store.selected_nbhds.get().length > 0) {
    if (viz_state.obs_store.selected_nbhds.get().includes(d.properties.cat)) {
      // if the cat is in the selected_nbhds, set the opacity to 255
      inst_opacity = 255;
    } else {
      // if the cat is not in the selected_nbhds, set the opacity to 50
      inst_opacity = 10;
    }
  } else {
    // if selected_nbhds is empty, set the opacity to 255
    inst_opacity = 255;
  }

  // add the opacity to the color
  inst_color.push(inst_opacity);

  return inst_color;

};

export const ini_nbhd_layer = (viz_state, visible) => {
  const nbhd_layer = new GeoJsonLayer({
    id: 'nbhd-layer',
    data: viz_state.nbhd.feature_collection,
    pickable: true,
    stroked: false,
    filled: true,
    getLineWidth: 1,
    getFillColor: (d) => get_nbhd_color(d, viz_state),
    opacity: 0.5,
    visible,
  });

  return nbhd_layer;
};

export const filter_cat_nbhd_feature_collection = (viz_state) => {
  let filt_features;

  if (viz_state.cats.selected_cats.length === 0) {
    filt_features = viz_state.nbhd.ini_feature_collection.features;
  } else {
    filt_features = viz_state.nbhd.ini_feature_collection.features.filter((d) =>
      viz_state.cats.selected_cats.includes(d.properties.cat)
    );
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

  // update selected_nbhds observable with the clicked nbhd unless
  // the clicked nbhd is already equal to selected_nbhds
  const prev_selected_nbhds = viz_state.obs_store.selected_nbhds.get();
  if (prev_selected_nbhds[0] === inst_cat && prev_selected_nbhds.length === 1) {
    viz_state.obs_store.selected_nbhds.set([]);
  } else {
    viz_state.obs_store.selected_nbhds.set([inst_cat]);
  }

  // refresh the nbhd layer
  refresh_layer(viz_state, layers_obj, 'nbhd_layer');

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
