export const get_layers_list = (layers_obj, close_up, _nbhd) => {
  let layers_list;
  const image_layers = layers_obj.image_layers || [];

  if (close_up) {
    layers_list = [
      layers_obj.background_layer,
      ...image_layers,
      layers_obj.path_layer,
      layers_obj.cell_layer,
      layers_obj.trx_layer,
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
