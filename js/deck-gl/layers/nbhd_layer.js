import { SolidPolygonLayer } from 'deck.gl';
import { hexToRgb } from '../../utils/hexToRgb';
import { update_selected_cats, update_cat } from '../../global_variables/cat';
import { update_selected_genes } from '../../global_variables/selected_genes';

export const ini_nbhd_layer = (viz_state, visible) => {
  const nbhd_layer = new SolidPolygonLayer({
    id: 'nbhd-layer',
    data: viz_state.nbhd.polygon_data,
    pickable: true,
    stroked: false,
    filled: true,
    getPolygon: (d) => d,
    getFillColor: (i) => hexToRgb(viz_state.nbhd.colors[i] || '#000000'),
    opacity: 0.5,
    visible,
  });

  return nbhd_layer;
};

export const update_nbhd_layer_data = (viz_state, layers_obj) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    data: viz_state.nbhd.polygon_data,
  });
};

const nbhd_layer_onclick = (
  info,
  _event,
  _deck_ist,
  _layers_obj,
  viz_state
) => {
  const inst_cat = viz_state.nbhd.cats[info.index];
  update_cat(viz_state.cats, 'cluster');
  update_selected_cats(viz_state.cats, [inst_cat], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);
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
