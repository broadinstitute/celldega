import { PointCloudLayer } from 'deck.gl';

import { getModelMatrixProps } from '../../utils/rotation';

const POSITION_SIZE = 3;
const COLOR_SIZE = 4;
const DEFAULT_CLUSTER_RGB = [128, 128, 128];

// Cells are colored by cluster only (no gene-expression mode at the cell
// tier — gene coloring is a neighborhood-fill-only feature per the spec).
// Reuses whichever `color_dict_cluster` the rest of the app already built
// (js/global_variables/meta_cluster.js) rather than recomputing colors.
export const build_nbhd_cloud_cell_color_buffer = (
  clusterIds,
  colorDictCluster = {}
) => {
  const colors = new Uint8Array(clusterIds.length * COLOR_SIZE);
  for (let i = 0; i < clusterIds.length; i++) {
    const rgb = colorDictCluster[clusterIds[i]] || DEFAULT_CLUSTER_RGB;
    colors[i * COLOR_SIZE] = rgb[0];
    colors[i * COLOR_SIZE + 1] = rgb[1];
    colors[i * COLOR_SIZE + 2] = rgb[2];
    colors[i * COLOR_SIZE + 3] = 255;
  }
  return colors;
};

const emptyPointCloudData = () => ({
  length: 0,
  attributes: {
    getPosition: { value: new Float32Array(0), size: POSITION_SIZE },
    getColor: { value: new Uint8Array(0), size: COLOR_SIZE, type: 'unorm8' },
  },
});

export const ini_nbhd_cloud_cell_layer = (viz_state) => {
  return new PointCloudLayer({
    id: 'nbhd-cloud-cell-layer',
    sizeUnits: 'meters',
    pointSize: 5,
    pickable: false,
    data: emptyPointCloudData(),
    opacity: 0,
    ...getModelMatrixProps(viz_state.rotation),
  });
};

// `mergedCells` is the output of `parse_cells_tables` (nbhd_cloud_tables.js):
// `{ length, positions, clusterIds, sliceIds }` for the current nearest-slice
// set.
export const refresh_nbhd_cloud_cell_layer_data = (
  viz_state,
  layers_obj,
  mergedCells
) => {
  const colors = build_nbhd_cloud_cell_color_buffer(
    mergedCells.clusterIds,
    viz_state.cats?.color_dict_cluster
  );

  layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
    data: {
      length: mergedCells.length,
      attributes: {
        getPosition: { value: mergedCells.positions, size: POSITION_SIZE },
        getColor: { value: colors, size: COLOR_SIZE, type: 'unorm8' },
      },
    },
  });
};

export const update_nbhd_cloud_cell_layer_opacity = (layers_obj, opacity) => {
  layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
    opacity,
  });
};
