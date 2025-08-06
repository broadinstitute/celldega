import * as d3 from 'd3';

export const scale_umap_data = (viz_state, cell_scatter_data_objects) => {

  console.log('scaling umap data');

  // scale umap values to be centered around the middle of the image x and y positions (max - min / 2)
  // use d3 to find the min and max of the flatCoordinateArray

  // if tech is 'Chromium' redefine placeholders for spatial max/min
  let x_min
  let x_max
  let y_min
  let y_max
  if (viz_state.img.landscape_parameters.technology === 'Chromium') {
    x_min = 0;
    x_max = 10000;
    y_min = 0;
    y_max = 10000;
  } else {
    x_min = viz_state.spatial.x_min;
    x_max = viz_state.spatial.x_max;
    y_min = viz_state.spatial.y_min;
    y_max = viz_state.spatial.y_max;
  }


  // take the smaller of the two ranges for x and y
  const x_range = x_max - x_min;
  const y_range = y_max - y_min;

  console.log(`x_min: ${x_min}, x_max: ${x_max}, y_min: ${y_min}, y_max: ${y_max}`);

  const range_max = Math.max(x_range, y_range);

  const x_mid = (x_max - x_min) / 2;
  const y_mid = (y_max - y_min) / 2;

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

  console.log('cell_scatter_data_objects', cell_scatter_data_objects);

  return cell_scatter_data_objects;
};
