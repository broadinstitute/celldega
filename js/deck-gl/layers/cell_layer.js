import * as d3 from 'd3';
import { ScatterplotLayer, PointCloudLayer } from 'deck.gl';

import {
  set_cell_cats,
  set_dict_cell_cats,
  update_selected_cats,
  update_cat,
} from '../../global_variables/cat';
import {
  set_cell_names_array,
  set_cell_name_to_index_map,
} from '../../global_variables/cell_names_array';
import { set_color_dict_gene } from '../../global_variables/color_dict_gene';
import { options } from '../../global_variables/fetch_options';
import { is_point_cloud_technology } from '../../global_variables/image_info';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import { get_scatter_data } from '../../read_parquet/get_scatter_data';
import { scale_umap_data } from '../../umap/scale_umap_data';
import { buildCellCompactData } from '../../utils/compact_data';
import { getModelMatrixProps } from '../../utils/rotation';

const POINT_CLOUD_POSITION_SIZE = 3;
const POINT_CLOUD_TRANSITION_LIMIT = 100000;

/**
 * Get the meta_cell key for a given cell name.
 * When cell_name_prefix is enabled, try both the full name and stripped name.
 * @param {string} name - Cell name from cell_names_array
 * @param {object} meta_cell - Meta cell data object
 * @param {boolean} cell_name_prefix - Whether cell_name_prefix mode is enabled
 * @returns {any[]|undefined} - Meta cell attributes or undefined if not found
 */
const get_meta_cell_attrs = (name, meta_cell, cell_name_prefix) => {
  // First try direct lookup
  if (meta_cell[name] !== undefined) {
    return meta_cell[name];
  }

  // If cell_name_prefix is enabled, try stripping the prefix
  if (cell_name_prefix && typeof name === 'string') {
    const idx = name.indexOf('_');
    if (idx >= 0) {
      const stripped = name.substring(idx + 1);
      if (meta_cell[stripped] !== undefined) {
        return meta_cell[stripped];
      }
    }
  }

  return undefined;
};

const is_point_cloud_viz = (viz_state) =>
  is_point_cloud_technology(viz_state.img?.landscape_parameters?.technology);

const toByte = (value) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return 0;
  }

  return Math.max(0, Math.min(255, Math.round(numericValue)));
};

const setColor = (colors, offset, r, g, b, a) => {
  colors[offset] = toByte(r);
  colors[offset + 1] = toByte(g);
  colors[offset + 2] = toByte(b);
  colors[offset + 3] = toByte(a);
};

export const set_spatial_bounds_from_flat_coordinates = (
  viz_state,
  flatCoordinateArray,
  dim,
  numRows
) => {
  if (numRows === 0) {
    viz_state.spatial.x_min = 0;
    viz_state.spatial.x_max = 0;
    viz_state.spatial.y_min = 0;
    viz_state.spatial.y_max = 0;
    viz_state.spatial.z_min = 0;
    viz_state.spatial.z_max = 0;
    return;
  }

  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  let zMin = Infinity;
  let zMax = -Infinity;

  for (let i = 0; i < numRows; i++) {
    const offset = i * dim;
    const x = flatCoordinateArray[offset];
    const y = flatCoordinateArray[offset + 1];
    xMin = Math.min(xMin, x);
    xMax = Math.max(xMax, x);
    yMin = Math.min(yMin, y);
    yMax = Math.max(yMax, y);

    if (dim === 3) {
      const z = flatCoordinateArray[offset + 2];
      zMin = Math.min(zMin, z);
      zMax = Math.max(zMax, z);
    }
  }

  viz_state.spatial.x_min = xMin;
  viz_state.spatial.x_max = xMax;
  viz_state.spatial.y_min = yMin;
  viz_state.spatial.y_max = yMax;

  viz_state.spatial.z_min = dim === 3 ? zMin : 0;
  viz_state.spatial.z_max = dim === 3 ? zMax : 0;
};

const build_point_cloud_position_buffer = (
  flatCoordinateArray,
  dim,
  numRows
) => {
  if (dim === POINT_CLOUD_POSITION_SIZE) {
    return new Float32Array(flatCoordinateArray);
  }

  const positions = new Float32Array(numRows * POINT_CLOUD_POSITION_SIZE);
  for (let i = 0; i < numRows; i++) {
    const sourceOffset = i * dim;
    const targetOffset = i * POINT_CLOUD_POSITION_SIZE;
    positions[targetOffset] = flatCoordinateArray[sourceOffset];
    positions[targetOffset + 1] = flatCoordinateArray[sourceOffset + 1];
    positions[targetOffset + 2] =
      dim > 2 ? flatCoordinateArray[sourceOffset + 2] : 0;
  }

  return positions;
};

export const set_point_cloud_cell_position_buffers = (
  viz_state,
  flatCoordinateArray,
  dim,
  numRows
) => {
  viz_state.spatial.cell_point_count = numRows;
  viz_state.spatial.cell_position_size = POINT_CLOUD_POSITION_SIZE;
  viz_state.spatial.cell_positions = build_point_cloud_position_buffer(
    flatCoordinateArray,
    dim,
    numRows
  );
  viz_state.spatial.cell_umap_positions = null;
};

export const set_point_cloud_umap_positions = (
  viz_state,
  cell_scatter_data_objects
) => {
  const positions = new Float32Array(
    cell_scatter_data_objects.length * POINT_CLOUD_POSITION_SIZE
  );

  cell_scatter_data_objects.forEach((cell, index) => {
    const offset = index * POINT_CLOUD_POSITION_SIZE;
    positions[offset] = cell.umap[0];
    positions[offset + 1] = cell.umap[1];
    positions[offset + 2] = 0;
  });

  viz_state.spatial.cell_umap_positions = positions;
};

const get_point_cloud_positions = (viz_state) => {
  if (
    viz_state.obs_store?.umap_state?.get() &&
    viz_state.spatial.cell_umap_positions
  ) {
    return viz_state.spatial.cell_umap_positions;
  }

  return viz_state.spatial.cell_positions;
};

export const update_cell_color_buffer = (viz_state) => {
  const { cats } = viz_state;
  const cellNames = cats.cell_names_array || [];
  const numCells = cellNames.length;
  const requiredLength = numCells * 4;

  if (
    !viz_state.spatial.cell_colors ||
    viz_state.spatial.cell_colors.length !== requiredLength
  ) {
    viz_state.spatial.cell_colors = new Uint8Array(requiredLength);
  }

  const colors = viz_state.spatial.cell_colors;
  const highlightedCells = viz_state.highlighted_cells ?? new Set();
  const hasHighlights = highlightedCells.size > 0;
  const selectedCats = cats.selected_cats || [];
  const selectedCatSet = new Set(selectedCats);
  const colorDict = cats.color_dict_cluster || {};
  const isClusterMode = cats.cat === 'cluster';
  const hasClusterFilter =
    !isClusterMode &&
    selectedCats.length > 0 &&
    selectedCats.some((cat) =>
      Object.prototype.hasOwnProperty.call(colorDict, cat)
    );

  for (let i = 0; i < numCells; i++) {
    const offset = i * 4;

    if (hasHighlights) {
      if (highlightedCells.has(cellNames[i])) {
        setColor(colors, offset, 0, 0, 255, 255);
      } else {
        setColor(colors, offset, 0, 0, 0, 0);
      }
      continue;
    }

    if (isClusterMode) {
      const instCat = cats.cell_cats?.[i];
      const instColor = colorDict[String(instCat)];
      const instOpacity =
        selectedCats.length === 0 || selectedCatSet.has(instCat) ? 255 : 0;

      if (Array.isArray(instColor)) {
        setColor(
          colors,
          offset,
          instColor[0],
          instColor[1],
          instColor[2],
          instOpacity
        );
      } else {
        setColor(colors, offset, 0, 0, 0, 0);
      }
    } else {
      const instCat = cats.cell_cats?.[i];
      const shouldShowExpression =
        !hasClusterFilter || selectedCatSet.has(instCat);
      const instExp = shouldShowExpression ? cats.cell_exp_array?.[i] : 0;
      setColor(colors, offset, 255, 0, 0, instExp);
    }
  }

  return colors;
};

export const get_point_cloud_cell_data = (viz_state) => {
  const positions = get_point_cloud_positions(viz_state) || new Float32Array();
  const colors =
    viz_state.spatial.cell_colors || update_cell_color_buffer(viz_state);

  return {
    length: viz_state.spatial.cell_point_count || 0,
    attributes: {
      getPosition: {
        value: positions,
        size: POINT_CLOUD_POSITION_SIZE,
      },
      getColor: {
        value: colors,
        size: 4,
        type: 'unorm8',
      },
    },
  };
};

export const refresh_point_cloud_cell_layer_data = (
  layers_obj,
  viz_state,
  layerProps = {}
) => {
  if (!is_point_cloud_viz(viz_state)) {
    return false;
  }

  update_cell_color_buffer(viz_state);
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    data: get_point_cloud_cell_data(viz_state),
    updateTriggers: {
      ...layers_obj.cell_layer.props.updateTriggers,
      getColor: [viz_state.selection_token],
    },
    ...layerProps,
  });

  return true;
};

const cell_layer_onclick = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  if (info.index === undefined || info.index < 0) {
    return;
  }

  const inst_cat = viz_state.cats.cell_cats[info.index];

  update_cat(viz_state.cats, 'cluster');

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });
  update_selected_cats(viz_state.cats, [inst_cat], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);
};

// transparent to red
export const get_cell_color = (cats, highlighted_cells, i, d) => {
  const highlight_set = highlighted_cells ?? new Set();
  const has_highlights = highlight_set.size > 0;
  const inst_cell = cats.cell_names_array[d.index];
  const is_highlighted = has_highlights && highlight_set.has(inst_cell);

  let base_color;

  if (cats.cat === 'cluster') {
    try {
      const inst_cat = cats.cell_cats[d.index];

      // Convert to string for consistent color lookup
      // (meta_cell values may be numbers, color_dict keys are always strings)
      let inst_color = cats.color_dict_cluster[String(inst_cat)];

      let inst_opacity =
        cats.selected_cats.length === 0 || cats.selected_cats.includes(inst_cat)
          ? 255
          : 0;

      // Check if inst_color is an array and log an error if it's not
      if (!Array.isArray(inst_color)) {
        inst_color = [0, 0, 0];
        inst_opacity = 0;
      }

      base_color = [...inst_color, inst_opacity];
    } catch {
      base_color = [0, 0, 0, 0]; // Return a default color with some opacity to handle the error gracefully
    }
  } else {
    // color cells based on gene expression
    try {
      const inst_exp = cats.cell_exp_array[d.index];

      // Check if we should filter to specific clusters (gene+cluster combination)
      // Only apply cluster filter if selected_cats contains actual cluster names
      // (not the gene name itself, which happens during normal gene selection)
      const has_cluster_filter =
        cats.selected_cats &&
        cats.selected_cats.length > 0 &&
        cats.selected_cats.some(
          (cat) => cats.color_dict_cluster && cat in cats.color_dict_cluster
        );

      if (has_cluster_filter) {
        const inst_cat = cats.cell_cats[d.index];
        if (!cats.selected_cats.includes(inst_cat)) {
          // Cell is not in the selected cluster(s) - make transparent
          base_color = [0, 0, 0, 0];
        } else {
          // Cell is in the selected cluster - show gene expression
          base_color = [255, 0, 0, inst_exp];
        }
      } else {
        // No cluster filter - show all cells with expression
        base_color = [255, 0, 0, inst_exp];
      }
    } catch {
      base_color = [255, 0, 0, 10]; // Return a default color with some opacity to handle the error gracefully
    }
  }

  if (!has_highlights) {
    return base_color;
  }

  if (is_highlighted) {
    return [0, 0, 255, 255];
  }

  // Non-selected cells are fully transparent when there are selected cells
  return [0, 0, 0, 0];
};

export const ini_cell_layer = async (base_url, viz_state) => {
  let cell_url;
  if (viz_state.seg.version === 'default') {
    cell_url = `${base_url}/cell_metadata.parquet`;
  } else {
    cell_url = `${base_url}/cell_metadata_${viz_state.seg.version}.parquet`;
  }

  const cell_arrow_table = await get_arrow_table(
    cell_url,
    options.fetch,
    viz_state.aws
  );

  set_cell_names_array(viz_state.cats, cell_arrow_table);

  viz_state.spatial.cell_scatter_data = get_scatter_data(cell_arrow_table);

  await set_color_dict_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  set_cell_name_to_index_map(viz_state.cats);

  if (viz_state.cats.has_meta_cell) {
    // look up the index of the inst_cell_attr in the meta_cell_attr array
    const inst_index = viz_state.cats.meta_cell_attr.indexOf(
      viz_state.cats.inst_cell_attr
    );

    // Use helper to handle cell_name_prefix matching
    const cell_name_prefix = viz_state.cell_name_prefix || false;

    viz_state.cats.cell_cats = viz_state.cats.cell_names_array.map((name) => {
      const attrs = get_meta_cell_attrs(
        name,
        viz_state.cats.meta_cell,
        cell_name_prefix
      );
      return attrs?.[inst_index] ?? 'N.A.';
    });
  } else {
    const cluster_arrow_table = await get_arrow_table(
      `${base_url}/cell_clusters${viz_state.seg.version && viz_state.seg.version !== 'default' ? `_${viz_state.seg.version}` : ''}/cluster.parquet`,
      options.fetch,
      viz_state.aws
    );
    set_cell_cats(viz_state.cats, cluster_arrow_table, 'cluster');
  }

  set_dict_cell_cats(viz_state.cats);

  const new_cell_names_array = cell_arrow_table.getChild('name').toArray();
  const flatCoordinateArray =
    viz_state.spatial.cell_scatter_data.attributes.getPosition.value;
  const dim =
    viz_state.spatial.cell_scatter_data.attributes.getPosition.size || 2;
  const numRows = viz_state.spatial.cell_scatter_data.length;
  const pointCloud = is_point_cloud_viz(viz_state);

  viz_state.combo_data.cell_compact = buildCellCompactData(
    new_cell_names_array,
    flatCoordinateArray,
    dim,
    viz_state.cats.dict_cell_cats
  );

  set_spatial_bounds_from_flat_coordinates(
    viz_state,
    flatCoordinateArray,
    dim,
    numRows
  );

  if (pointCloud) {
    set_point_cloud_cell_position_buffers(
      viz_state,
      flatCoordinateArray,
      dim,
      numRows
    );
  }

  let cell_scatter_data_objects;
  if (viz_state.umap.has_umap) {
    const flatCoordinateArray_umap = new Float64Array(
      viz_state.cats.cell_names_array.flatMap((cell_id) => {
        let coords;
        if (!viz_state.umap.umap[cell_id]) {
          coords = [0, 0];
        } else {
          coords = viz_state.umap.umap[cell_id];
        }

        return coords;
      })
    );

    // convert to easier to use objects
    cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
      name: viz_state.cats.cell_names_array[i],
      position:
        dim === 3
          ? [
              flatCoordinateArray[i * dim],
              flatCoordinateArray[i * dim + 1],
              flatCoordinateArray[i * dim + 2],
            ]
          : [flatCoordinateArray[i * dim], flatCoordinateArray[i * dim + 1]],
      umap: [
        flatCoordinateArray_umap[i * 2],
        flatCoordinateArray_umap[i * 2 + 1],
      ],
    }));

    cell_scatter_data_objects = scale_umap_data(
      viz_state,
      cell_scatter_data_objects
    );

    if (pointCloud) {
      set_point_cloud_umap_positions(viz_state, cell_scatter_data_objects);
    }
  } else if (!pointCloud) {
    cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
      name: viz_state.cats.cell_names_array[i],
      position:
        dim === 3
          ? [
              flatCoordinateArray[i * dim],
              flatCoordinateArray[i * dim + 1],
              flatCoordinateArray[i * dim + 2],
            ]
          : [flatCoordinateArray[i * dim], flatCoordinateArray[i * dim + 1]],
    }));
  } else {
    cell_scatter_data_objects = null;
  }

  viz_state.spatial.center_x =
    (viz_state.spatial.x_max + viz_state.spatial.x_min) / 2;
  viz_state.spatial.center_y =
    (viz_state.spatial.y_max + viz_state.spatial.y_min) / 2;
  if (dim === 3) {
    viz_state.spatial.center_z =
      (viz_state.spatial.z_max + viz_state.spatial.z_min) / 2;
    viz_state.spatial.data_depth =
      viz_state.spatial.z_max - viz_state.spatial.z_min;
  }

  viz_state.spatial.data_width =
    viz_state.spatial.x_max - viz_state.spatial.x_min;
  viz_state.spatial.data_height =
    viz_state.spatial.y_max - viz_state.spatial.y_min;

  // get the width of viz_state.root
  const _root_width = viz_state.root.clientWidth;
  const _root_height = viz_state.root.clientHeight;

  const canvas_width = viz_state.root.clientWidth; // 1000
  const canvas_height = viz_state.containers.root_dim.height; //500

  viz_state.spatial.scale_x = canvas_width / viz_state.spatial.data_width;
  viz_state.spatial.scale_y = canvas_height / viz_state.spatial.data_height;
  viz_state.spatial.scale = Math.min(
    viz_state.spatial.scale_x,
    viz_state.spatial.scale_y
  );

  // calculate ini x, y, zoom if technology is not Chromium
  if (viz_state.img.landscape_parameters.technology !== 'Chromium') {
    viz_state.spatial.ini_zoom = Math.log2(viz_state.spatial.scale) * 1.01;
    viz_state.spatial.ini_x = viz_state.spatial.center_x;
    viz_state.spatial.ini_y = viz_state.spatial.center_y;
    if (dim === 3) {
      viz_state.spatial.ini_z = viz_state.spatial.center_z;
    }
  } else {
    viz_state.spatial.ini_zoom = Math.log2(canvas_width / 5000) * 0.95;
    viz_state.spatial.ini_x = 5000;
    viz_state.spatial.ini_y = 5000;
  }

  viz_state.spatial.cell_scatter_data_objects = cell_scatter_data_objects;

  const transitions =
    !pointCloud || numRows < POINT_CLOUD_TRANSITION_LIMIT
      ? {
          getPosition: {
            duration: 3000,
            easing: d3.easeCubic,
          },
        }
      : undefined;

  let cell_layer;
  if (pointCloud) {
    update_cell_color_buffer(viz_state);
    cell_layer = new PointCloudLayer({
      id: 'cell-layer',
      sizeUnits: 'meters',
      pointSize: 5,
      pickable: true,
      data: get_point_cloud_cell_data(viz_state),
      transitions,
      updateTriggers: {
        getPosition: [viz_state.obs_store.umap_state.get()],
        getColor: [viz_state.selection_token],
      },
      opacity: 1,
      ...getModelMatrixProps(viz_state.rotation),
    });
  } else {
    cell_layer = new ScatterplotLayer({
      id: 'cell-layer',
      radiusMinPixels: 1,
      getRadius: 5.0,
      pickable: true,
      getFillColor: (i, d) =>
        get_cell_color(viz_state.cats, viz_state.highlighted_cells, i, d),
      data: viz_state.spatial.cell_scatter_data_objects,
      transitions,
      getPosition: (d) =>
        viz_state.obs_store.umap_state.get() ? d.umap : d.position,
      updateTriggers: {
        getPosition: [viz_state.obs_store.umap_state.get()],
        getFillColor: [viz_state.selection_token],
      },
      ...getModelMatrixProps(viz_state.rotation),
    });
  }

  return cell_layer;
};

export const set_cell_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    onClick: (event, d) =>
      cell_layer_onclick(event, d, deck_ist, layers_obj, viz_state),
  });
};

export const new_toggle_cell_layer_visibility = (layers_obj, visible) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    visible,
  });
};

const POINT_SIZE_SCALE_FACTOR = 2;

export const update_cell_layer_radius = (layers_obj, radius, viz_state) => {
  if (is_point_cloud_viz(viz_state)) {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      pointSize: radius / POINT_SIZE_SCALE_FACTOR,
    });
  } else {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      getRadius: radius,
    });
  }
};

export const update_cell_pickable_state = (layers_obj, pickable) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    pickable,
  });
};

export const toggle_spatial_umap = (_deck_ist, layers_obj, viz_state) => {
  if (is_point_cloud_viz(viz_state)) {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      data: get_point_cloud_cell_data(viz_state),
      updateTriggers: {
        ...layers_obj.cell_layer.props.updateTriggers,
        getPosition: [viz_state.obs_store.umap_state.get()],
      },
    });
    return;
  }

  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    updateTriggers: {
      getPosition: [viz_state.obs_store.umap_state.get()],
    },
  });
};
