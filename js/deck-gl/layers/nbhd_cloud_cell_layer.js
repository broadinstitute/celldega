import { PointCloudLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import { parse_cells_tables } from '../../read_parquet/nbhd_cloud_tables';
import { getModelMatrixProps } from '../../utils/rotation';

const POSITION_SIZE = 3;
const COLOR_SIZE = 4;
const DEFAULT_CLUSTER_RGB = [128, 128, 128];

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
    opacity: 1,
    ...getModelMatrixProps(viz_state.rotation),
  });
};

const filterPositionsByCluster = (mergedCells, clusterId) => {
  const positions = new Float32Array(mergedCells.length * POSITION_SIZE);
  let count = 0;
  for (let i = 0; i < mergedCells.length; i++) {
    if (String(mergedCells.clusterIds[i]) !== clusterId) {
      continue;
    }
    positions[count * POSITION_SIZE] = mergedCells.positions[i * POSITION_SIZE];
    positions[count * POSITION_SIZE + 1] =
      mergedCells.positions[i * POSITION_SIZE + 1];
    positions[count * POSITION_SIZE + 2] =
      mergedCells.positions[i * POSITION_SIZE + 2];
    count += 1;
  }
  return {
    length: count,
    positions: positions.subarray(0, count * POSITION_SIZE),
  };
};

const buildConstantColorBuffer = (length, rgb) => {
  const colors = new Uint8Array(length * COLOR_SIZE);
  for (let i = 0; i < length; i++) {
    colors[i * COLOR_SIZE] = rgb[0];
    colors[i * COLOR_SIZE + 1] = rgb[1];
    colors[i * COLOR_SIZE + 2] = rgb[2];
    colors[i * COLOR_SIZE + 3] = 255;
  }
  return colors;
};

// Backs the per-neighborhood bar's click (bar_plot.js). A neighborhood is
// one (slice, cluster) pair, so showing its cells is always a small, bounded
// fetch+filter -- never the whole dataset: fetch (and cache, per slice)
// `cells/by_slice/slice_<id>.parquet`, then filter to the picked cluster
// client-side. Clicking the same neighborhood again clears the layer.
export const select_nbhd_cloud_neighborhood_cells = async (
  neighborhoodId,
  sliceId,
  clusterId,
  viz_state,
  layers_obj
) => {
  const { nbhd_cloud } = viz_state;
  const isReset = neighborhoodId === nbhd_cloud.selected_cell_neighborhood_id;

  if (isReset) {
    nbhd_cloud.selected_cell_neighborhood_id = null;
    layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
      data: emptyPointCloudData(),
    });
    return;
  }

  nbhd_cloud.cell_cache_by_slice ??= new Map();
  let mergedCells = nbhd_cloud.cell_cache_by_slice.get(sliceId);
  if (!mergedCells) {
    const table = await get_arrow_table(
      `${viz_state.global_base_url}/nbhd_cloud/cells/by_slice/slice_${sliceId}.parquet`,
      options.fetch,
      viz_state.aws ?? null
    );
    mergedCells = parse_cells_tables([table]);
    nbhd_cloud.cell_cache_by_slice.set(sliceId, mergedCells);
  }

  const filtered = filterPositionsByCluster(mergedCells, String(clusterId));
  const rgb =
    viz_state.cats?.color_dict_cluster?.[String(clusterId)] ||
    DEFAULT_CLUSTER_RGB;
  const colors = buildConstantColorBuffer(filtered.length, rgb);

  nbhd_cloud.selected_cell_neighborhood_id = neighborhoodId;
  layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
    data: {
      length: filtered.length,
      attributes: {
        getPosition: { value: filtered.positions, size: POSITION_SIZE },
        getColor: { value: colors, size: COLOR_SIZE, type: 'unorm8' },
      },
    },
  });
};
