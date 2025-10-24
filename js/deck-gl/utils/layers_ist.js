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
      layers_obj.edit_layer,
    ];
  } else {
    layers_list = [
      layers_obj.background_layer,
      ...layers_obj.image_layers,
      layers_obj.cell_layer,
      layers_obj.nbhd_layer,
      layers_obj.edit_layer,
    ];
  }

  if (layers_obj.scale_bar_bar_layer) {
    layers_list.push(layers_obj.scale_bar_bar_layer);
  }

  if (layers_obj.scale_bar_text_layer) {
    layers_list.push(layers_obj.scale_bar_text_layer);
  }

  return layers_list;
};
