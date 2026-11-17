import {
  is_active_image_source,
  is_orbit_technology,
} from '../../global_variables/image_info';

export const get_layers_list = (layers_obj, close_up, viz_state) => {
  // Omit the inactive source so TileLayer does not fetch its hidden tiles.
  const image_layers = (layers_obj.image_layers || []).filter(
    (layer) =>
      !layer.props.imageSource ||
      is_active_image_source(layer.props.imageSource, layers_obj.image_source)
  );
  const isPointCloud = is_orbit_technology(
    viz_state?.img?.landscape_parameters?.technology
  );

  // Hide, rather than omit, close-up layers when zoomed out. deck.gl finalizes
  // layers that leave the list and cannot initialize that instance again, so
  // re-adding it on zoom-in fails an assertion and can draw freed GPU buffers.
  const close_up_layer = (layer) => {
    if (isPointCloud || !layer) return null;
    return close_up ? layer : layer.clone({ visible: false });
  };

  return [
    layers_obj.background_layer,
    ...image_layers,
    close_up_layer(layers_obj.path_layer),
    layers_obj.cell_layer,
    close_up_layer(layers_obj.trx_layer),
    layers_obj.nbhd_layer,
    layers_obj.nbhd_cloud_shapes_layer,
    layers_obj.nbhd_cloud_cell_layer,
    layers_obj.edit_layer,
    // Pins (points of interest from Snapshots) stay on top.
    layers_obj.pin_layer,
  ].filter(Boolean);
};
