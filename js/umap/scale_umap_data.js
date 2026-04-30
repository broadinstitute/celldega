import * as d3 from 'd3';

import { is_point_cloud_technology } from '../global_variables/image_info';

const getUmapTarget = (viz_state) => {
  let x_min;
  let x_max;
  let y_min;
  let y_max;
  const { technology } = viz_state.img.landscape_parameters;
  if (technology === 'Chromium' || is_point_cloud_technology(technology)) {
    x_min = 0;
    x_max = 10000;
    y_min = 0;
    y_max = 10000;
  } else {
    ({ x_min, x_max, y_min, y_max } = viz_state.spatial);
  }

  const x_range = x_max - x_min;
  const y_range = y_max - y_min;

  return {
    range_max: Math.max(x_range, y_range),
    x_mid: x_range / 2,
    y_mid: y_range / 2,
  };
};

export const scale_umap_positions = (viz_state, positions, stride = 2) => {
  if (!positions || positions.length === 0) {
    return positions;
  }

  const { range_max, x_mid, y_mid } = getUmapTarget(viz_state);
  let umap_x_min = Infinity;
  let umap_x_max = -Infinity;
  let umap_y_min = Infinity;
  let umap_y_max = -Infinity;

  for (let offset = 0; offset < positions.length; offset += stride) {
    const x = positions[offset];
    const y = positions[offset + 1];
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      continue;
    }

    umap_x_min = Math.min(umap_x_min, x);
    umap_x_max = Math.max(umap_x_max, x);
    umap_y_min = Math.min(umap_y_min, y);
    umap_y_max = Math.max(umap_y_max, y);
  }

  if (!Number.isFinite(umap_x_min) || !Number.isFinite(umap_y_min)) {
    return positions;
  }

  const umap_x_range = umap_x_max - umap_x_min;
  const umap_y_range = umap_y_max - umap_y_min;
  const scaled_min = -range_max / 2;

  for (let offset = 0; offset < positions.length; offset += stride) {
    const x = positions[offset];
    const y = positions[offset + 1];

    positions[offset] =
      umap_x_range > 0
        ? ((x - umap_x_min) / umap_x_range) * range_max + x_mid + scaled_min
        : x_mid;
    positions[offset + 1] =
      umap_y_range > 0
        ? ((y - umap_y_min) / umap_y_range) * range_max + y_mid + scaled_min
        : y_mid;
  }

  return positions;
};

export const scale_umap_data = (viz_state, cell_scatter_data_objects) => {
  // scale umap values to be centered around the middle of the image x and y positions (max - min / 2)
  // use d3 to find the min and max of the flatCoordinateArray

  // if tech is 'Chromium' redefine placeholders for spatial max/min
  const { range_max, x_mid, y_mid } = getUmapTarget(viz_state);

  let umap_x_min = d3.min(cell_scatter_data_objects.map((d) => d.umap[0]));
  let umap_x_max = d3.max(cell_scatter_data_objects.map((d) => d.umap[0]));
  let umap_y_min = d3.min(cell_scatter_data_objects.map((d) => d.umap[1]));
  let umap_y_max = d3.max(cell_scatter_data_objects.map((d) => d.umap[1]));

  const umap_x_range = umap_x_max - umap_x_min;
  const umap_y_range = umap_y_max - umap_y_min;

  // scale the umap values to be within range_max and centered about x_mid and y_mid
  cell_scatter_data_objects.forEach((d) => {
    d.umap[0] = ((d.umap[0] - umap_x_min) / umap_x_range) * range_max;
    d.umap[1] = ((d.umap[1] - umap_y_min) / umap_y_range) * range_max;
  });

  umap_x_min = d3.min(cell_scatter_data_objects.map((d) => d.umap[0]));
  umap_x_max = d3.max(cell_scatter_data_objects.map((d) => d.umap[0]));
  umap_y_min = d3.min(cell_scatter_data_objects.map((d) => d.umap[1]));
  umap_y_max = d3.max(cell_scatter_data_objects.map((d) => d.umap[1]));

  const umap_x_mid = (umap_x_max - umap_x_min) / 2;
  const umap_y_mid = (umap_y_max - umap_y_min) / 2;

  const x_diff = x_mid - umap_x_mid;
  const y_diff = y_mid - umap_y_mid;

  cell_scatter_data_objects.forEach((d) => {
    d.umap[0] = d.umap[0] + x_diff;
    d.umap[1] = d.umap[1] + y_diff;
  });

  return cell_scatter_data_objects;
};
