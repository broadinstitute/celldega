import { EditableGeoJsonLayer, DrawPolygonMode, ViewMode } from '@deck.gl-community/editable-layers';

import { get_layers_list } from '../utils/layers_ist';

export const ini_edit_layer = (viz_state) => {
  return new EditableGeoJsonLayer({
    id: 'edit-layer',
    data: viz_state.nbhd.feature_collection,
    mode: ViewMode,
    selectedFeatureIndexes: [],
    getFillColor: (d) => d.properties.color || [200, 0, 0, 80],
    pickable: true,
    visible: viz_state.obs_store.nbhd_edit_mode.get(),
    opacity: 0.3,
  });
};

export const update_edit_visibility = (layers_obj, visible) => {
  layers_obj.edit_layer = layers_obj.edit_layer.clone({ visible });
};

export const set_edit_layer_on_edit = (deck_ist, layers_obj, viz_state) => {
  layers_obj.edit_layer = layers_obj.edit_layer.clone({
    onEdit: ({ updatedData }) => {
      viz_state.nbhd.feature_collection = updatedData;
      layers_obj.edit_layer = layers_obj.edit_layer.clone({
        data: viz_state.nbhd.feature_collection,
        mode: ViewMode,
      });
      viz_state.model.set('nbhd_geojson', viz_state.nbhd.feature_collection);
      viz_state.model.save_changes();
      const layers_list = get_layers_list(layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: layers_list });
    },
  });
};

export const set_edit_layer_on_click = (deck_ist, layers_obj, viz_state) => {
  layers_obj.edit_layer = layers_obj.edit_layer.clone({
    onClick: (info) => {
      if (info.object) {
        viz_state.nbhd.selected_index = info.index;
      } else {
        viz_state.nbhd.selected_index = null;
      }
    },
  });
};

export const start_sketch_mode = (layers_obj) => {
  layers_obj.edit_layer = layers_obj.edit_layer.clone({
    mode: DrawPolygonMode,
  });
};

export const delete_selected_feature = (deck_ist, layers_obj, viz_state) => {
  const idx =
    viz_state.nbhd.selected_index != null
      ? viz_state.nbhd.selected_index
      : viz_state.nbhd.feature_collection.features.length - 1;
  if (idx >= 0) {
    viz_state.nbhd.feature_collection.features.splice(idx, 1);
    viz_state.nbhd.selected_index = null;
    layers_obj.edit_layer = layers_obj.edit_layer.clone({
      data: viz_state.nbhd.feature_collection,
    });
    viz_state.model.set('nbhd_geojson', viz_state.nbhd.feature_collection);
    viz_state.model.save_changes();
    const layers_list = get_layers_list(layers_obj, viz_state.close_up);
    deck_ist.setProps({ layers: layers_list });
  }
};
