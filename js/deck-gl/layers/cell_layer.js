/* eslint-disable no-console */
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
import { scale_umap_positions } from '../../umap/scale_umap_data';
import {
  buildCellCompactData,
  createEmptyCellCompact,
} from '../../utils/compact_data';
import { getModelMatrixProps } from '../../utils/rotation';
import { get_point_cloud_source_index } from '../utils/point_cloud_indices';

import {
  CELL_COLOR_SIZE,
  getVizCellColorContext,
  isCellVisible,
  update_cell_color_buffer,
  writeCellColor,
} from './cell_color';

export { get_cell_color, update_cell_color_buffer } from './cell_color';

const POINT_CLOUD_POSITION_SIZE = 3;
const POINT_CLOUD_DEBUG_SAMPLE_SIZE = 5;
const POINT_CLOUD_HOVER_LOG_INTERVAL_MS = 750;
const SPATIAL_BOUNDS_SAMPLE_LIMIT = 10000;
const Z_OUTLIER_SPAN_RATIO = 10;

let pointCloudDataLogCount = 0;
let pointCloudHoverLogTime = 0;
let pointCloudHoverLogIndex = null;

const get_table_field_names = (table) =>
  table?.schema?.fields?.map((field) => field.name) || [];

const preview_array = (values, count = POINT_CLOUD_DEBUG_SAMPLE_SIZE) =>
  Array.from(values || []).slice(0, count);

const preview_positions = (
  positions,
  size = POINT_CLOUD_POSITION_SIZE,
  count = POINT_CLOUD_DEBUG_SAMPLE_SIZE
) =>
  Array.from(
    { length: Math.min(count, Math.floor((positions?.length || 0) / size)) },
    (_value, index) =>
      preview_array(positions.subarray(index * size, index * size + size), size)
  );

const get_point_cloud_source_sample = (
  viz_state,
  context,
  positions,
  count = POINT_CLOUD_DEBUG_SAMPLE_SIZE
) => {
  const sampleCount = Math.min(count, context.cellNames.length || 0);

  return Array.from({ length: sampleCount }, (_value, index) => {
    const cat = viz_state.cats.cell_cats?.[index];
    const positionOffset = index * POINT_CLOUD_POSITION_SIZE;

    return {
      index,
      name: context.cellNames[index],
      cat,
      color: context.colorDict?.[String(cat)] || null,
      position: preview_array(
        positions?.subarray?.(
          positionOffset,
          positionOffset + POINT_CLOUD_POSITION_SIZE
        ),
        POINT_CLOUD_POSITION_SIZE
      ),
      visible: isCellVisible(context, index),
    };
  });
};

const summarize_point_cloud_data = (viz_state, data, context, positions) => {
  const positionAttr = data.attributes?.getPosition;
  const colorAttr = data.attributes?.getColor;

  return {
    call: pointCloudDataLogCount,
    technology: viz_state.img?.landscape_parameters?.technology,
    length: data.length,
    full_cell_point_count: viz_state.spatial.cell_point_count,
    visible_cell_count: viz_state.spatial.visible_cell_count,
    cell_names_count: context.cellNames.length,
    cell_cats_count: viz_state.cats.cell_cats?.length || 0,
    color_dict_size: Object.keys(context.colorDict || {}).length,
    cat_mode: viz_state.cats.cat,
    selected_cats: preview_array(context.selectedCats),
    has_highlights: context.hasHighlights,
    positions: {
      constructor: positionAttr?.value?.constructor?.name,
      values: positionAttr?.value?.length || 0,
      size: positionAttr?.size,
      rows: positionAttr?.value
        ? Math.floor(positionAttr.value.length / (positionAttr.size || 1))
        : 0,
      sample: preview_positions(positionAttr?.value, positionAttr?.size),
    },
    colors: {
      constructor: colorAttr?.value?.constructor?.name,
      values: colorAttr?.value?.length || 0,
      size: colorAttr?.size,
      rows: colorAttr?.value
        ? Math.floor(colorAttr.value.length / (colorAttr.size || 1))
        : 0,
      sample: preview_positions(colorAttr?.value, colorAttr?.size),
    },
    bounds: {
      x: [viz_state.spatial.x_min, viz_state.spatial.x_max],
      y: [viz_state.spatial.y_min, viz_state.spatial.y_max],
      z: [viz_state.spatial.z_min, viz_state.spatial.z_max],
      raw_z: [viz_state.spatial.z_min_raw, viz_state.spatial.z_max_raw],
      z_center_robust: viz_state.spatial.z_center_robust,
      z_bounds_outlier_clamped: viz_state.spatial.z_bounds_outlier_clamped,
      width: viz_state.spatial.data_width,
      height: viz_state.spatial.data_height,
      depth: viz_state.spatial.data_depth,
    },
    initial_view: {
      x: viz_state.spatial.ini_x,
      y: viz_state.spatial.ini_y,
      z: viz_state.spatial.ini_z,
      zoom: viz_state.spatial.ini_zoom,
      scale: viz_state.spatial.scale,
    },
    source_sample: get_point_cloud_source_sample(viz_state, context, positions),
  };
};

const log_point_cloud_debug = (label, details) => {
  console.log(`[celldega point-cloud] ${label}`, details);
};

const warn_point_cloud_debug = (label, details) => {
  console.warn(`[celldega point-cloud] ${label}`, details);
};

const percentile = (sortedValues, fraction) => {
  if (sortedValues.length === 0) {
    return 0;
  }

  const index = Math.min(
    sortedValues.length - 1,
    Math.max(0, Math.floor((sortedValues.length - 1) * fraction))
  );
  return sortedValues[index];
};

const log_missing_point_cloud_colors = (viz_state, context) => {
  const missing = get_point_cloud_source_sample(viz_state, context, null, 20)
    .filter((cell) => cell.cat !== null && cell.color === null)
    .slice(0, POINT_CLOUD_DEBUG_SAMPLE_SIZE);

  if (missing.length > 0) {
    warn_point_cloud_debug('sample cells have no cluster color', {
      missing,
      color_dict_keys_sample: preview_array(
        Object.keys(context.colorDict || {})
      ),
      selected_cats: preview_array(context.selectedCats),
      cat_mode: viz_state.cats.cat,
    });
  }
};

const assert_binary_attribute_lengths = (label, data) => {
  const rows_for = (attr) => {
    if (!attr?.value) return Infinity;
    const size = attr.size || 1;
    return Math.floor(attr.value.length / size);
  };

  const rows = Object.entries(data.attributes || {}).map(([name, attr]) => ({
    name,
    rows: rows_for(attr),
    items: attr?.value?.length,
    size: attr?.size || 1,
    data_length: data.length,
  }));

  const too_short = rows.filter((row) => row.rows < data.length);

  if (too_short.length > 0) {
    console.error(`[${label}] binary attribute shorter than data.length`, {
      data,
      rows,
      too_short,
    });
    throw new Error(`[${label}] binary attribute shorter than data.length`);
  }

  // console.table(rows)
  return data;
};

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
  const zSamples = [];
  const zSampleStride = Math.max(
    1,
    Math.floor(numRows / SPATIAL_BOUNDS_SAMPLE_LIMIT)
  );

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
      if (Number.isFinite(z) && i % zSampleStride === 0) {
        zSamples.push(z);
      }
    }
  }

  let robustZMin = dim === 3 ? zMin : 0;
  let robustZMax = dim === 3 ? zMax : 0;
  let robustZCenter = dim === 3 ? (zMin + zMax) / 2 : 0;
  let useRobustZ = false;

  if (dim === 3 && zSamples.length > 0) {
    zSamples.sort((a, b) => a - b);
    robustZMin = percentile(zSamples, 0.01);
    robustZMax = percentile(zSamples, 0.99);
    robustZCenter = percentile(zSamples, 0.5);

    const xySpan = Math.max(xMax - xMin, yMax - yMin, 1);
    const rawZDepth = zMax - zMin;
    const robustZDepth = robustZMax - robustZMin;
    useRobustZ =
      Number.isFinite(rawZDepth) &&
      rawZDepth > xySpan * Z_OUTLIER_SPAN_RATIO &&
      robustZDepth < rawZDepth;

    if (useRobustZ) {
      warn_point_cloud_debug(
        'z bounds look outlier-dominated; using robust z view center',
        {
          raw_z: [zMin, zMax],
          robust_z: [robustZMin, robustZMax],
          robust_z_center: robustZCenter,
          xy_span: xySpan,
          sample_count: zSamples.length,
        }
      );
    }
  }

  viz_state.spatial.x_min = xMin;
  viz_state.spatial.x_max = xMax;
  viz_state.spatial.y_min = yMin;
  viz_state.spatial.y_max = yMax;

  viz_state.spatial.z_min_raw = dim === 3 ? zMin : 0;
  viz_state.spatial.z_max_raw = dim === 3 ? zMax : 0;
  viz_state.spatial.z_min = dim === 3 ? (useRobustZ ? robustZMin : zMin) : 0;
  viz_state.spatial.z_max = dim === 3 ? (useRobustZ ? robustZMax : zMax) : 0;
  viz_state.spatial.z_center_robust = dim === 3 ? robustZCenter : 0;
  viz_state.spatial.z_bounds_outlier_clamped = useRobustZ;
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

  log_point_cloud_debug('position buffer initialized', {
    input_rows: numRows,
    input_dim: dim,
    input_values: flatCoordinateArray?.length || 0,
    buffer_values: viz_state.spatial.cell_positions.length,
    buffer_rows: Math.floor(
      viz_state.spatial.cell_positions.length / POINT_CLOUD_POSITION_SIZE
    ),
    sample: preview_positions(viz_state.spatial.cell_positions),
  });
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

export const set_point_cloud_umap_positions_from_names = (
  viz_state,
  cellNames,
  numRows = cellNames.length
) => {
  const positions = new Float32Array(numRows * POINT_CLOUD_POSITION_SIZE);
  const umap = viz_state.umap?.umap || {};

  for (let index = 0; index < numRows; index++) {
    const coords = umap[cellNames[index]];
    const offset = index * POINT_CLOUD_POSITION_SIZE;
    positions[offset] = Number(coords?.[0]) || 0;
    positions[offset + 1] = Number(coords?.[1]) || 0;
    positions[offset + 2] = 0;
  }

  viz_state.spatial.cell_umap_positions = scale_umap_positions(
    viz_state,
    positions,
    POINT_CLOUD_POSITION_SIZE
  );
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

const shouldCompactPointCloudCells = (context) => {
  if (context.hasHighlights) {
    return true;
  }

  if (context.isClusterMode) {
    return context.selectedCats.length > 0;
  }

  return true;
};

const ensureCompactBuffer = (spatial, key, Type, requiredLength) => {
  const bufferKey = `${key}_buffer`;
  if (!spatial[bufferKey] || spatial[bufferKey].length !== requiredLength) {
    spatial[bufferKey] = new Type(requiredLength);
  }

  spatial[key] = spatial[bufferKey].subarray(0, requiredLength);
  return spatial[key];
};

const clearPointCloudVisibleCellIndices = (viz_state, visibleCount) => {
  viz_state.spatial.visible_cell_positions = null;
  viz_state.spatial.visible_cell_positions_buffer = null;
  viz_state.spatial.visible_cell_colors = null;
  viz_state.spatial.visible_cell_colors_buffer = null;
  viz_state.spatial.visible_cell_indices = null;
  viz_state.spatial.visible_cell_indices_buffer = null;
  viz_state.spatial.visible_cell_count = visibleCount;
};

const get_compact_point_cloud_cell_data = (viz_state, positions, context) => {
  const fullCount = Math.min(
    viz_state.spatial.cell_point_count || 0,
    context.cellNames.length,
    Math.floor(positions.length / POINT_CLOUD_POSITION_SIZE)
  );
  let visibleCount = 0;

  for (let i = 0; i < fullCount; i++) {
    if (isCellVisible(context, i)) {
      visibleCount += 1;
    }
  }

  if (visibleCount === fullCount) {
    clearPointCloudVisibleCellIndices(viz_state, fullCount);
    const data = {
      length: fullCount,
      attributes: {
        getPosition: {
          value: positions,
          size: POINT_CLOUD_POSITION_SIZE,
        },
        getColor: {
          value: update_cell_color_buffer(viz_state).subarray(
            0,
            fullCount * CELL_COLOR_SIZE
          ),
          size: CELL_COLOR_SIZE,
          type: 'unorm8',
        },
      },
    };

    pointCloudDataLogCount += 1;
    log_point_cloud_debug(
      'data built without compaction after visibility scan',
      summarize_point_cloud_data(viz_state, data, context, positions)
    );
    log_missing_point_cloud_colors(viz_state, context);
    return data;
  }

  const compactPositions = ensureCompactBuffer(
    viz_state.spatial,
    'visible_cell_positions',
    Float32Array,
    visibleCount * POINT_CLOUD_POSITION_SIZE
  );
  const compactColors = ensureCompactBuffer(
    viz_state.spatial,
    'visible_cell_colors',
    Uint8Array,
    visibleCount * CELL_COLOR_SIZE
  );
  const visibleCellIndices = ensureCompactBuffer(
    viz_state.spatial,
    'visible_cell_indices',
    Uint32Array,
    visibleCount
  );

  let targetIndex = 0;
  for (let sourceIndex = 0; sourceIndex < fullCount; sourceIndex++) {
    if (!isCellVisible(context, sourceIndex)) {
      continue;
    }

    const sourcePositionOffset = sourceIndex * POINT_CLOUD_POSITION_SIZE;
    const targetPositionOffset = targetIndex * POINT_CLOUD_POSITION_SIZE;
    compactPositions[targetPositionOffset] = positions[sourcePositionOffset];
    compactPositions[targetPositionOffset + 1] =
      positions[sourcePositionOffset + 1];
    compactPositions[targetPositionOffset + 2] =
      positions[sourcePositionOffset + 2];

    writeCellColor(
      context,
      sourceIndex,
      compactColors,
      targetIndex * CELL_COLOR_SIZE
    );
    visibleCellIndices[targetIndex] = sourceIndex;
    targetIndex += 1;
  }

  viz_state.spatial.visible_cell_count = visibleCount;

  const data = {
    length: visibleCount,
    attributes: {
      getPosition: {
        value: compactPositions,
        size: POINT_CLOUD_POSITION_SIZE,
      },
      getColor: {
        value: compactColors,
        size: CELL_COLOR_SIZE,
        type: 'unorm8',
      },
    },
  };

  pointCloudDataLogCount += 1;
  log_point_cloud_debug('data built with compaction', {
    ...summarize_point_cloud_data(viz_state, data, context, compactPositions),
    full_count: fullCount,
    visible_count: visibleCount,
    visible_source_indices_sample: preview_array(visibleCellIndices),
  });
  log_missing_point_cloud_colors(viz_state, context);
  return data;
};

export const get_point_cloud_cell_data = (viz_state) => {
  const positions = get_point_cloud_positions(viz_state) || new Float32Array();
  const context = getVizCellColorContext(viz_state);
  const fullCount = Math.min(
    viz_state.spatial.cell_point_count || 0,
    context.cellNames.length,
    Math.floor(positions.length / POINT_CLOUD_POSITION_SIZE)
  );

  if (shouldCompactPointCloudCells(context)) {
    return get_compact_point_cloud_cell_data(viz_state, positions, context);
  }

  const colors = update_cell_color_buffer(viz_state);
  clearPointCloudVisibleCellIndices(viz_state, fullCount);

  const data = {
    length: fullCount,
    attributes: {
      getPosition: {
        value: positions,
        size: POINT_CLOUD_POSITION_SIZE,
      },
      getColor: {
        value: colors.subarray(0, fullCount * CELL_COLOR_SIZE),
        size: CELL_COLOR_SIZE,
        type: 'unorm8',
      },
    },
  };

  pointCloudDataLogCount += 1;
  log_point_cloud_debug(
    'data built',
    summarize_point_cloud_data(viz_state, data, context, positions)
  );
  log_missing_point_cloud_colors(viz_state, context);
  return data;
};

export const set_scatterplot_umap_positions_from_names = (
  viz_state,
  cellNames,
  numRows = cellNames.length
) => {
  const positions = new Float64Array(numRows * 2);
  const umap = viz_state.umap?.umap || {};

  for (let index = 0; index < numRows; index++) {
    const coords = umap[cellNames[index]];
    const offset = index * 2;
    positions[offset] = Number(coords?.[0]) || 0;
    positions[offset + 1] = Number(coords?.[1]) || 0;
  }

  viz_state.spatial.cell_umap_scatter_positions = scale_umap_positions(
    viz_state,
    positions,
    2
  );
};

const get_scatterplot_positions = (viz_state) => {
  if (
    viz_state.obs_store?.umap_state?.get() &&
    viz_state.spatial.cell_umap_scatter_positions
  ) {
    return {
      value: viz_state.spatial.cell_umap_scatter_positions,
      size: 2,
    };
  }

  return (
    viz_state.spatial.cell_scatter_data?.attributes?.getPosition || {
      value: new Float64Array(),
      size: 2,
    }
  );
};

export const get_scatterplot_cell_data = (viz_state) => {
  const positions = get_scatterplot_positions(viz_state);
  const positionSize = positions.size || 2;
  const fullCount = Math.min(
    viz_state.spatial.cell_scatter_data?.length || 0,
    viz_state.cats.cell_names_array?.length || 0,
    Math.floor(positions.value.length / positionSize)
  );

  const position_values =
    positions.value instanceof Float32Array
      ? positions.value
      : new Float32Array(positions.value);

  return assert_binary_attribute_lengths('scatterplot-cell', {
    length: fullCount,
    attributes: {
      getPosition: {
        value: position_values,
        size: positionSize,
        type: 'float32',
      },
      getFillColor: {
        value: update_cell_color_buffer(viz_state).subarray(
          0,
          fullCount * CELL_COLOR_SIZE
        ),
        size: CELL_COLOR_SIZE,
        type: 'unorm8',
      },
    },
  });
};

export const refresh_cell_layer_data = (
  layers_obj,
  viz_state,
  layerProps = {}
) => {
  const { updateTriggers: extraUpdateTriggers, ...stableLayerProps } =
    layerProps;
  const isPointCloud = is_point_cloud_viz(viz_state);

  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    transitions: false,
    ...stableLayerProps,
    data: isPointCloud
      ? get_point_cloud_cell_data(viz_state)
      : get_scatterplot_cell_data(viz_state),
    updateTriggers: {
      ...layers_obj.cell_layer.props.updateTriggers,
      getPosition: [viz_state.obs_store.umap_state.get()],
      ...(isPointCloud
        ? { getColor: [viz_state.selection_token] }
        : { getFillColor: [viz_state.selection_token] }),
      ...extraUpdateTriggers,
    },
  });

  return true;
};

export const refresh_point_cloud_cell_layer_data = (
  layers_obj,
  viz_state,
  layerProps = {}
) => {
  if (!is_point_cloud_viz(viz_state)) {
    return false;
  }

  return refresh_cell_layer_data(layers_obj, viz_state, layerProps);
};

const cell_layer_onclick = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const sourceIndex =
    info.index === undefined || info.index < 0
      ? -1
      : get_point_cloud_source_index(viz_state, info.index);

  log_point_cloud_debug('click', {
    picked: info.picked,
    layer_id: info.layer?.id,
    index: info.index,
    source_index: sourceIndex,
    pixel: [info.x, info.y],
    coordinate: info.coordinate,
    name:
      sourceIndex >= 0 ? viz_state.cats.cell_names_array[sourceIndex] : null,
    cat: sourceIndex >= 0 ? viz_state.cats.cell_cats[sourceIndex] : null,
    selected_cats_before: preview_array(viz_state.cats.selected_cats),
  });

  if (info.index === undefined || info.index < 0) {
    return;
  }

  if (sourceIndex < 0) {
    return;
  }

  const inst_cat = viz_state.cats.cell_cats[sourceIndex];

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

const cell_layer_onhover = (info, _event, viz_state) => {
  if (!is_point_cloud_viz(viz_state)) {
    return;
  }

  const now = Date.now();
  if (
    info.index === pointCloudHoverLogIndex &&
    now - pointCloudHoverLogTime < POINT_CLOUD_HOVER_LOG_INTERVAL_MS
  ) {
    return;
  }

  pointCloudHoverLogIndex = info.index;
  pointCloudHoverLogTime = now;

  const sourceIndex =
    info.index === undefined || info.index < 0
      ? -1
      : get_point_cloud_source_index(viz_state, info.index);

  log_point_cloud_debug('hover', {
    picked: info.picked,
    layer_id: info.layer?.id,
    index: info.index,
    source_index: sourceIndex,
    pixel: [info.x, info.y],
    coordinate: info.coordinate,
    name:
      sourceIndex >= 0 ? viz_state.cats.cell_names_array[sourceIndex] : null,
    cat: sourceIndex >= 0 ? viz_state.cats.cell_cats[sourceIndex] : null,
  });
};

export const ini_cell_layer = async (base_url, viz_state) => {
  let cell_url;
  const pointCloud = is_point_cloud_viz(viz_state);

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

  if (pointCloud) {
    log_point_cloud_debug('cell metadata loaded', {
      url: cell_url,
      rows: cell_arrow_table?.numRows,
      fields: get_table_field_names(cell_arrow_table),
    });
  }

  set_cell_names_array(viz_state.cats, cell_arrow_table);

  viz_state.spatial.cell_scatter_data = get_scatter_data(cell_arrow_table);

  await set_color_dict_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  if (pointCloud && viz_state.vector_name_integer) {
    viz_state.cats.cell_name_to_index_map = new Map();
  } else {
    set_cell_name_to_index_map(viz_state.cats);
  }

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
    const cluster_url = `${base_url}/cell_clusters${viz_state.seg.version && viz_state.seg.version !== 'default' ? `_${viz_state.seg.version}` : ''}/cluster.parquet`;
    const cluster_arrow_table = await get_arrow_table(
      cluster_url,
      options.fetch,
      viz_state.aws
    );
    if (pointCloud) {
      log_point_cloud_debug('cluster metadata loaded', {
        url: cluster_url,
        rows: cluster_arrow_table?.numRows,
        fields: get_table_field_names(cluster_arrow_table),
      });
    }
    set_cell_cats(viz_state.cats, cluster_arrow_table, 'cluster');
  }

  if (pointCloud) {
    viz_state.cats.dict_cell_cats = {};
    viz_state.cats.has_dict_cell_cats = false;
  } else {
    set_dict_cell_cats(viz_state.cats);
  }

  const new_cell_names_array = viz_state.cats.cell_names_array;
  const flatCoordinateArray =
    viz_state.spatial.cell_scatter_data.attributes.getPosition.value;
  const dim =
    viz_state.spatial.cell_scatter_data.attributes.getPosition.size || 2;
  const numRows = viz_state.spatial.cell_scatter_data.length;

  if (pointCloud) {
    log_point_cloud_debug('cell state after parquet normalization', {
      cell_names_count: viz_state.cats.cell_names_array.length,
      cell_names_sample: preview_array(viz_state.cats.cell_names_array),
      cell_cats_count: viz_state.cats.cell_cats.length,
      cell_cats_sample: preview_array(viz_state.cats.cell_cats),
      color_dict_size: Object.keys(viz_state.cats.color_dict_cluster || {})
        .length,
      color_dict_sample: preview_array(
        Object.entries(viz_state.cats.color_dict_cluster || {})
      ),
      cluster_counts_sample: preview_array(viz_state.cats.cluster_counts),
      scatter_rows: numRows,
      scatter_position_values: flatCoordinateArray.length,
      scatter_dim: dim,
    });
  }

  viz_state.combo_data.cell_compact = pointCloud
    ? createEmptyCellCompact()
    : buildCellCompactData(
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

  if (viz_state.umap.has_umap) {
    if (pointCloud) {
      set_point_cloud_umap_positions_from_names(
        viz_state,
        viz_state.cats.cell_names_array,
        numRows
      );
    } else {
      set_scatterplot_umap_positions_from_names(
        viz_state,
        viz_state.cats.cell_names_array,
        numRows
      );
    }
  } else {
    viz_state.spatial.cell_umap_scatter_positions = null;
  }

  viz_state.spatial.center_x =
    (viz_state.spatial.x_max + viz_state.spatial.x_min) / 2;
  viz_state.spatial.center_y =
    (viz_state.spatial.y_max + viz_state.spatial.y_min) / 2;
  // if (dim === 3) {
  //   viz_state.spatial.center_z =
  //     (viz_state.spatial.z_max + viz_state.spatial.z_min) / 2;
  //   viz_state.spatial.data_depth =
  //     viz_state.spatial.z_max - viz_state.spatial.z_min;
  // }
  if (dim === 3) {
    const rawCenterZ =
      (viz_state.spatial.z_max + viz_state.spatial.z_min) / 2;

    const robustCenterZ =
      is_point_cloud_viz(viz_state) &&
      Number.isFinite(viz_state.spatial.z_center_robust)
        ? viz_state.spatial.z_center_robust
        : rawCenterZ;

    viz_state.spatial.center_z = robustCenterZ;

    // Keep raw depth for diagnostics, but do not let it drive camera target.
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

  viz_state.spatial.cell_scatter_data_objects = null;

  // const transitions = pointCloud
  //   ? undefined
  //   : {
  //       getPosition: {
  //         duration: 3000,
  //         easing: d3.easeCubic,
  //       },
  //     };

  const transitions = false;

  let cell_layer;
  if (pointCloud) {
    const pointCloudData = get_point_cloud_cell_data(viz_state);
    log_point_cloud_debug('creating PointCloudLayer', {
      id: 'cell-layer',
      data_length: pointCloudData.length,
      pointSize: 50,
      sizeUnits: 'meters',
      pickable: true,
      opacity: 1,
      position_rows: Math.floor(
        pointCloudData.attributes.getPosition.value.length /
          pointCloudData.attributes.getPosition.size
      ),
      color_rows: Math.floor(
        pointCloudData.attributes.getColor.value.length /
          pointCloudData.attributes.getColor.size
      ),
    });
    cell_layer = new PointCloudLayer({
      id: 'cell-layer',
      sizeUnits: 'meters',
      pointSize: 5,
      pickable: true,
      data: pointCloudData,
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
      data: get_scatterplot_cell_data(viz_state),
      transitions,
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
    onHover: (event, d) => cell_layer_onhover(event, d, viz_state),
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

// export const toggle_spatial_umap = (_deck_ist, layers_obj, viz_state) => {
//   if (is_point_cloud_viz(viz_state)) {
//     layers_obj.cell_layer = layers_obj.cell_layer.clone({
//       data: get_point_cloud_cell_data(viz_state),
//       updateTriggers: {
//         ...layers_obj.cell_layer.props.updateTriggers,
//         getPosition: [viz_state.obs_store.umap_state.get()],
//       },
//     });
//     return;
//   }

//   layers_obj.cell_layer = layers_obj.cell_layer.clone({
//     data: get_scatterplot_cell_data(viz_state),
//     updateTriggers: {
//       ...layers_obj.cell_layer.props.updateTriggers,
//       getPosition: [viz_state.obs_store.umap_state.get()],
//     },
//   });
// };

const spatial_umap_transitions = (viz_state) =>
  viz_state.umap?.has_umap
    ? {
        getPosition: {
          duration: 3000,
          easing: d3.easeCubic,
        },
      }
    : false;

export const toggle_spatial_umap = (_deck_ist, layers_obj, viz_state) => {
  const transitions = spatial_umap_transitions(viz_state);

  if (is_point_cloud_viz(viz_state)) {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      data: get_point_cloud_cell_data(viz_state),
      transitions,
      updateTriggers: {
        ...layers_obj.cell_layer.props.updateTriggers,
        getPosition: [viz_state.obs_store.umap_state.get()],
      },
    });
    return;
  }

  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    data: get_scatterplot_cell_data(viz_state),
    transitions,
    updateTriggers: {
      ...layers_obj.cell_layer.props.updateTriggers,
      getPosition: [viz_state.obs_store.umap_state.get()],
    },
  });
};
