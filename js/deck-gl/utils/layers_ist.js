export const get_layers_list = (layers_obj, close_up, _nbhd) => {
  let layers_list;

  if (close_up) {
    layers_list = [
      layers_obj.background_layer,
      ...layers_obj.image_layers,
      layers_obj.path_layer,
      layers_obj.cell_layer,
      layers_obj.trx_layer,
      layers_obj.nbhd_layer,
    ];
  } else {
    layers_list = [
      layers_obj.background_layer,
      ...layers_obj.image_layers,
      layers_obj.cell_layer,
      layers_obj.nbhd_layer,
    ];
  }

  return layers_list;
};
