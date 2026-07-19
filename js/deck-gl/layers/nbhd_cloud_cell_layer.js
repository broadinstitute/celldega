import { PointCloudLayer } from 'deck.gl';

import { toExpressionByte } from '../../global_variables/cell_exp_array';
import { options } from '../../global_variables/fetch_options';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import {
  parse_cells_tables,
  parse_gene_cells_table,
} from '../../read_parquet/nbhd_cloud_tables';
import { getModelMatrixProps } from '../../utils/rotation';

const POSITION_SIZE = 3;
const COLOR_SIZE = 4;
const DEFAULT_CLUSTER_RGB = [128, 128, 128];
// Same red hue as gene-shapes fill (nbhd_cloud_shapes_layer.js) and per-cell
// gene coloring elsewhere -- kept as a local copy rather than a shared
// import since nbhd_cloud_shapes_layer.js already imports FROM this module
// (importing back would be circular).
const GENE_COLOR_RGB = [255, 0, 0];
// Cell centroids sit on top of (and can visually crowd) the shape they
// belong to -- scaling the NBHD slider's value down a bit even at 100%
// keeps them legible against the shape underneath, while still tracking
// the same slider so they dim/brighten together.
const CELL_OPACITY_SCALE = 0.7;

// Gene-mode cells already carry their own per-cell alpha (expression-based,
// baked into the color buffer below) -- the TRX slider (gene_fill_opacity)
// is a further multiplier on top via deck.gl's layer-level `opacity`, same
// mechanism as cluster mode, just without the extra CELL_OPACITY_SCALE
// dampening (that was reasoned specifically for solid-color cluster cells
// sitting on a solid-ish cluster shape; gene shapes are already a flat,
// independently-tuned opacity of their own).
const get_cell_layer_opacity = (viz_state) => {
  const { nbhd_cloud } = viz_state;
  if (nbhd_cloud.gene_shapes_mode) {
    return nbhd_cloud.gene_fill_opacity ?? 1;
  }
  return (nbhd_cloud.manual_fill_opacity ?? 1) * CELL_OPACITY_SCALE;
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
    opacity: get_cell_layer_opacity(viz_state),
    // deck.gl enables WebGL depth testing globally (Deck._setDevice), so
    // two semi-transparent surfaces at different Z depth-fight: whichever
    // is closer to the camera wins outright (the other's fragment is
    // discarded, not blended) -- and which one that is flips with camera
    // angle. A per-layer `parameters` override skips depth testing just for
    // this layer's draw call, so cell centroids always render on top of
    // the shapes layer (drawn earlier -- see get_layers_list) regardless of
    // viewing direction, at their true spatial position (no Z offset
    // needed to fake visibility from one side).
    parameters: { depthTest: false },
    ...getModelMatrixProps(viz_state.rotation),
  });
};

// Optionally narrows to one or more slices (client-side -- the by_cluster
// file already carries `slice_id`). `sliceIdFilter` is null/empty to mean
// "every slice".
const buildFilteredPositions = (mergedCells, sliceIdFilter) => {
  const positions = new Float32Array(mergedCells.length * POSITION_SIZE);
  let count = 0;
  for (let i = 0; i < mergedCells.length; i++) {
    if (sliceIdFilter && !sliceIdFilter.has(mergedCells.sliceIds[i])) {
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

// Like buildFilteredPositions, but also carries each cell's expression
// value through the filter (needed to color-code by expression afterward).
const buildFilteredGeneCells = (mergedCells, sliceIdFilter) => {
  const positions = new Float32Array(mergedCells.length * POSITION_SIZE);
  const expressions = new Float32Array(mergedCells.length);
  let count = 0;
  for (let i = 0; i < mergedCells.length; i++) {
    if (sliceIdFilter && !sliceIdFilter.has(mergedCells.sliceIds[i])) {
      continue;
    }
    positions[count * POSITION_SIZE] = mergedCells.positions[i * POSITION_SIZE];
    positions[count * POSITION_SIZE + 1] =
      mergedCells.positions[i * POSITION_SIZE + 1];
    positions[count * POSITION_SIZE + 2] =
      mergedCells.positions[i * POSITION_SIZE + 2];
    expressions[count] = mergedCells.expressions[i];
    count += 1;
  }
  return {
    length: count,
    positions: positions.subarray(0, count * POSITION_SIZE),
    expressions: expressions.subarray(0, count),
  };
};

// Red, alpha proportional to that cell's own expression relative to the
// gene's whole-tissue single-cell max (same toExpressionByte convention as
// per-cell gene coloring and the pre-flattening gene-shapes fill) -- this is
// the "peppering" that grounds the coarse alpha shape in real single-cell
// positions/magnitudes.
const buildExpressionColorBuffer = (expressions, maxExpression) => {
  const colors = new Uint8Array(expressions.length * COLOR_SIZE);
  for (let i = 0; i < expressions.length; i++) {
    const alpha = toExpressionByte(expressions[i], maxExpression);
    colors[i * COLOR_SIZE] = GENE_COLOR_RGB[0];
    colors[i * COLOR_SIZE + 1] = GENE_COLOR_RGB[1];
    colors[i * COLOR_SIZE + 2] = GENE_COLOR_RGB[2];
    colors[i * COLOR_SIZE + 3] = alpha;
  }
  return colors;
};

// Cluster selection (not per-neighborhood) drives cell display -- called
// after `viz_state.nbhd_cloud.selected_cluster_ids` changes (bar click or
// shape click) *and* after `selected_slice_ids` changes (slice bar), since
// an active slice isolation should narrow whichever cluster is already
// selected. Reads current state rather than taking params, so either
// trigger can call it without needing to know about the other.
export const refresh_nbhd_cloud_cluster_cells = async (
  viz_state,
  layers_obj
) => {
  const { nbhd_cloud } = viz_state;
  const clusterId = [...(nbhd_cloud.selected_cluster_ids ?? [])][0];

  if (clusterId == null) {
    layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
      data: emptyPointCloudData(),
      opacity: get_cell_layer_opacity(viz_state),
    });
    return;
  }

  nbhd_cloud.cell_cache_by_cluster ??= new Map();
  let mergedCells = nbhd_cloud.cell_cache_by_cluster.get(clusterId);
  if (!mergedCells) {
    const table = await get_arrow_table(
      `${viz_state.global_base_url}/nbhd_cloud/cells/by_cluster/cluster_${clusterId}.parquet`,
      options.fetch,
      viz_state.aws ?? null
    );
    mergedCells = parse_cells_tables([table]);
    nbhd_cloud.cell_cache_by_cluster.set(clusterId, mergedCells);
  }

  const sliceIdFilter =
    nbhd_cloud.selected_slice_ids?.size > 0
      ? nbhd_cloud.selected_slice_ids
      : null;
  const filtered = buildFilteredPositions(mergedCells, sliceIdFilter);
  const rgb =
    viz_state.cats?.color_dict_cluster?.[clusterId] || DEFAULT_CLUSTER_RGB;
  const colors = buildConstantColorBuffer(filtered.length, rgb);

  layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
    data: {
      length: filtered.length,
      attributes: {
        getPosition: { value: filtered.positions, size: POSITION_SIZE },
        getColor: { value: colors, size: COLOR_SIZE, type: 'unorm8' },
      },
    },
    opacity: get_cell_layer_opacity(viz_state),
  });
};

// Gene selection (gene-shapes mode) drives cell display the same way
// cluster selection does above -- called after
// `viz_state.nbhd_cloud.selected_gene` changes *and* after
// `selected_slice_ids` changes, since an active slice isolation should
// narrow whichever gene is already selected. "Peppers" the gene's alpha
// shape with a bounded, expression-colored subset of its own real
// highest-expressing cells (see `write_gene_shapes_from_cbg`'s
// `max_cells`) -- grounding the coarse polygon in actual single-cell
// positions rather than leaving it a plain filled shape.
export const refresh_nbhd_cloud_gene_cells = async (viz_state, layers_obj) => {
  const { nbhd_cloud } = viz_state;
  const gene = nbhd_cloud.selected_gene;

  if (!gene) {
    layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
      data: emptyPointCloudData(),
      opacity: get_cell_layer_opacity(viz_state),
    });
    return;
  }

  nbhd_cloud.gene_cell_cache ??= new Map();
  let mergedCells = nbhd_cloud.gene_cell_cache.get(gene);
  if (!mergedCells) {
    const table = await get_arrow_table(
      `${viz_state.global_base_url}/nbhd_cloud/cells/by_gene/${gene}.parquet`,
      options.fetch,
      viz_state.aws ?? null
    );
    mergedCells = parse_gene_cells_table(table);
    nbhd_cloud.gene_cell_cache.set(gene, mergedCells);
  }

  const sliceIdFilter =
    nbhd_cloud.selected_slice_ids?.size > 0
      ? nbhd_cloud.selected_slice_ids
      : null;
  const filtered = buildFilteredGeneCells(mergedCells, sliceIdFilter);
  const maxExpression = nbhd_cloud.available_gene_shapes?.get(gene) ?? 0;
  const colors = buildExpressionColorBuffer(
    filtered.expressions,
    maxExpression
  );

  layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
    data: {
      length: filtered.length,
      attributes: {
        getPosition: { value: filtered.positions, size: POSITION_SIZE },
        getColor: { value: colors, size: COLOR_SIZE, type: 'unorm8' },
      },
    },
    opacity: get_cell_layer_opacity(viz_state),
  });
};

// Lets the NBHD/TRX sliders update cell centroid opacity immediately,
// without waiting on a full cell-data refresh (which only runs on
// selection/slice changes, not on every slider tick). Mode-aware via
// get_cell_layer_opacity, so the same helper backs both cluster-mode
// (NBHD slider) and gene-mode (TRX slider) callers.
export const update_nbhd_cloud_cell_layer_opacity = (layers_obj, viz_state) => {
  layers_obj.nbhd_cloud_cell_layer = layers_obj.nbhd_cloud_cell_layer.clone({
    opacity: get_cell_layer_opacity(viz_state),
  });
};
