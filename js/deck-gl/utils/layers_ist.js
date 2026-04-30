import { is_point_cloud_technology } from '../../global_variables/image_info';

export const get_layers_list = (layers_obj, close_up, viz_state) => {
  let layers_list;
  const image_layers = layers_obj.image_layers || [];
  const isPointCloud = is_point_cloud_technology(
    viz_state?.img?.landscape_parameters?.technology
  );

  if (close_up) {
    layers_list = [
      layers_obj.background_layer,
      ...image_layers,
      isPointCloud ? null : layers_obj.path_layer,
      layers_obj.cell_layer,
      isPointCloud ? null : layers_obj.trx_layer,
      layers_obj.nbhd_layer,
      layers_obj.edit_layer,
    ];
  } else {
    layers_list = [
      layers_obj.background_layer,
      ...image_layers,
      layers_obj.cell_layer,
      layers_obj.nbhd_layer,
      layers_obj.edit_layer,
    ];
  }

  return layers_list.filter(Boolean);
};
