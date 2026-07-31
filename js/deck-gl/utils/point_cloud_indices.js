import { is_orbit_technology } from '../../global_variables/image_info';

export const get_point_cloud_source_index = (viz_state, layerIndex) => {
  if (layerIndex === undefined || layerIndex < 0) {
    return -1;
  }

  const technology = viz_state.img?.landscape_parameters?.technology;
  if (!is_orbit_technology(technology)) {
    return layerIndex;
  }

  const visibleCellIndices = viz_state.spatial?.visible_cell_indices;
  if (!visibleCellIndices) {
    return layerIndex;
  }

  return visibleCellIndices[layerIndex] ?? -1;
};
