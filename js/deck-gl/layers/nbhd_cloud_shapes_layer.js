import { GeoJsonLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import {
  parse_gene_expression_table,
  parse_gene_shapes_table_to_features,
} from '../../read_parquet/nbhd_cloud_tables';
import { hexToRgb } from '../../utils/hexToRgb';
import { refresh_layer } from '../../utils/refresh_layer';
import { getModelMatrixProps } from '../../utils/rotation';

import { refresh_nbhd_cloud_cluster_cells } from './nbhd_cloud_cell_layer';

// Reuses the same red-hue, alpha-encodes-expression convention already used
// for per-cell gene coloring (cell_color.js) rather than a separate
// colormap, so a neighborhood doesn't visually change representation when it
// crossfades into cells at the same zoom level.
const GENE_COLOR_RGB = [255, 0, 0];

// Applied to every shape outside the selected cluster (bar click or direct
// shape click) when a selection is active -- fully transparent, not just
// dimmed, so only the selected cluster's shapes are visible.
const UNSELECTED_DIM_FACTOR = 0;

// The manifest of genes with precomputed alpha shapes (a small curated
// marker-gene list, see write_gene_shapes) is missing for most datasets --
// that's the normal case, not an error, so this resolves to an empty Set
// rather than throwing on a 404/network failure.
export const fetch_available_gene_shapes = async (base_url, aws) => {
  const url = `${base_url}/nbhd_cloud/gene_shapes/available_genes.json`;
  try {
    const response = aws
      ? await aws.fetch(url)
      : await fetch(url, options.fetch);
    if (!response.ok) {
      return new Set();
    }
    const genes = await response.json();
    return new Set(genes);
  } catch {
    return new Set();
  }
};

export const is_nbhd_cloud_gene_color_mode = (nbhd_cloud) =>
  nbhd_cloud?.selected_gene != null;

export const get_nbhd_cloud_fill_color = (feature, viz_state) => {
  const { nbhd_cloud } = viz_state;
  const manualFraction = nbhd_cloud.manual_fill_opacity ?? 1;

  // Gene-shapes mode: a different feature set entirely (one polygon per
  // (slice, gene) from a curated marker-gene list, see write_gene_shapes),
  // each carrying its own `mean_expression` directly -- no cluster_id, no
  // neighborhood_id lookup, and no cluster-selection dimming (there's no
  // cluster concept here to dim against).
  if (nbhd_cloud.gene_shapes_mode) {
    const mean = feature.properties.mean_expression ?? 0;
    const maxMean = nbhd_cloud.gene_shapes_max_mean || 0;
    const expressionFraction = maxMean > 0 ? Math.min(1, mean / maxMean) : 0;
    const alpha = Math.round(255 * expressionFraction * manualFraction);
    return [...GENE_COLOR_RGB, alpha];
  }

  const clusterId = String(feature.properties.cluster_id);
  const hasSelection = (nbhd_cloud.selected_cluster_ids?.size ?? 0) > 0;
  const isSelected = nbhd_cloud.selected_cluster_ids?.has(clusterId);
  const selectionFactor =
    !hasSelection || isSelected ? 1 : UNSELECTED_DIM_FACTOR;

  const effectiveFraction = manualFraction * selectionFactor;

  if (is_nbhd_cloud_gene_color_mode(nbhd_cloud)) {
    const stats = nbhd_cloud.gene_stats?.get(
      feature.properties.neighborhood_id
    );
    const mean = stats?.mean ?? 0;
    const maxMean = nbhd_cloud.selected_gene_max_mean || 0;
    const expressionFraction = maxMean > 0 ? Math.min(1, mean / maxMean) : 0;
    const alpha = Math.round(255 * expressionFraction * effectiveFraction);
    return [...GENE_COLOR_RGB, alpha];
  }

  const rgb = hexToRgb(feature.properties.color);
  return [...rgb, Math.round(255 * effectiveFraction)];
};

// No outline -- with dozens to hundreds of overlapping-in-projection
// polygons across slices, a stroke on every one reads as visual noise more
// than as useful structure.
export const ini_nbhd_cloud_shapes_layer = (viz_state, features = []) => {
  return new GeoJsonLayer({
    id: 'nbhd-cloud-shapes-layer',
    data: { type: 'FeatureCollection', features },
    pickable: true,
    stroked: false,
    filled: true,
    getFillColor: (d) => get_nbhd_cloud_fill_color(d, viz_state),
    opacity: 1,
    // Many overlapping semi-transparent polygons stack at different Z
    // (one per slice). With WebGL depth testing on (deck.gl's global
    // default) and no back-to-front sort among them, overlapping fragments
    // depth-fight instead of blending -- the jagged/torn edges where
    // slices overlap. Skipping depth testing for this layer trades exact
    // per-fragment depth ordering for consistent alpha blending, which
    // reads far better than the fighting it replaces.
    parameters: { depthTest: false },
    ...getModelMatrixProps(viz_state.rotation),
  });
};

// Backs the SLICE bar's isolate behavior (bar_plot.js) -- swaps the
// rendered feature set rather than dimming, so an unselected slice's shapes
// are genuinely gone (not just faint).
export const update_nbhd_cloud_shapes_data = (layers_obj, features) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      data: { type: 'FeatureCollection', features },
    }
  );
};

// Restores the shapes layer to the cluster-based shapes (respecting any
// active slice isolation) -- called whenever gene-shapes mode is exited,
// since that mode swapped `data` to a wholly different feature set (one
// polygon per (slice, gene) instead of per (slice, cluster)).
const restore_cluster_shapes_data = (viz_state, layers_obj) => {
  const { nbhd_cloud } = viz_state;
  const hasSliceSelection = (nbhd_cloud.selected_slice_ids?.size ?? 0) > 0;
  const features = hasSliceSelection
    ? nbhd_cloud.shapes_features.filter((feature) =>
        nbhd_cloud.selected_slice_ids.has(feature.properties.slice_id)
      )
    : nbhd_cloud.shapes_features;
  update_nbhd_cloud_shapes_data(layers_obj, features);
};

export const update_nbhd_cloud_shapes_fill_color = (layers_obj, viz_state) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      getFillColor: (d) => get_nbhd_cloud_fill_color(d, viz_state),
      updateTriggers: {
        getFillColor: [
          viz_state.nbhd_cloud.selected_gene,
          viz_state.nbhd_cloud.gene_shapes_mode,
          viz_state.nbhd_cloud.manual_fill_opacity,
          viz_state.nbhd_cloud.selected_cluster_ids?.size ?? 0,
        ],
      },
    }
  );
};

// Backs both the per-cluster bar's click (bar_plot.js) and a direct shape
// click (below) -- single-select: clicking the already-selected cluster
// clears the selection. Selecting a cluster applies across every slice, not
// just the slice the click happened to land on.
//
// Cluster selection and gene coloring are mutually exclusive modes --
// picking a cluster always reverts to cluster-color ("nbhd") highlighting,
// clearing whatever gene was selected (the bar's own opacity reset happens
// at the call sites, which also own the gene bar's DOM).
export const toggle_nbhd_cloud_cluster_selection = (
  clusterId,
  viz_state,
  layers_obj
) => {
  const { nbhd_cloud } = viz_state;
  nbhd_cloud.selected_cluster_ids ??= new Set();

  const isReset = nbhd_cloud.selected_cluster_ids.has(clusterId);
  nbhd_cloud.selected_cluster_ids.clear();
  if (!isReset) {
    nbhd_cloud.selected_cluster_ids.add(clusterId);
  }

  nbhd_cloud.selected_gene = null;
  nbhd_cloud.gene_stats = null;
  nbhd_cloud.selected_gene_max_mean = 0;

  if (nbhd_cloud.gene_shapes_mode) {
    nbhd_cloud.gene_shapes_mode = false;
    nbhd_cloud.gene_shapes_max_mean = 0;
    restore_cluster_shapes_data(viz_state, layers_obj);
  }

  update_nbhd_cloud_shapes_fill_color(layers_obj, viz_state);
};

// Direct shape-click selection -- same effect as clicking that shape's
// cluster in the bar graph (dim other clusters, load cell centroids for
// this one across every slice), so either interaction path stays in sync.
const nbhd_cloud_shapes_onclick = async (
  info,
  _event,
  layers_obj,
  viz_state
) => {
  const clusterId = String(info.object?.properties?.cluster_id ?? '');
  if (!clusterId) {
    return;
  }

  toggle_nbhd_cloud_cluster_selection(clusterId, viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');

  await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_cell_layer');

  const hasSelection =
    (viz_state.nbhd_cloud.selected_cluster_ids?.size ?? 0) > 0;
  viz_state.nbhd_cloud.svg_bar_cluster
    ?.selectAll('rect')
    .style('opacity', (bar) =>
      !hasSelection ||
      viz_state.nbhd_cloud.selected_cluster_ids.has(String(bar.name))
        ? 1.0
        : 0.2
    );
  // Gene mode was just cleared (toggle_nbhd_cloud_cluster_selection) -- the
  // gene bar's own highlight is this handler's responsibility, same as the
  // cluster bar's above.
  viz_state.genes.svg_bar_gene?.selectAll('rect').style('opacity', 1.0);
};

export const set_nbhd_cloud_shapes_layer_onclick = (layers_obj, viz_state) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      onClick: (info, event) =>
        nbhd_cloud_shapes_onclick(info, event, layers_obj, viz_state),
    }
  );
};

// Backs the gene bar's click (and gene search) -- three-way branch:
//
// 1. Clicking the already-selected gene again reverts to cluster color
//    (and, if it was showing gene shapes, restores the cluster shapes data).
// 2. A gene in `viz_state.nbhd_cloud.available_gene_shapes` (the small
//    curated marker-gene list from `write_gene_shapes`) swaps the whole
//    shapes layer to that gene's own precomputed alpha shapes -- built from
//    expressing cells, not the cluster/slice geometry -- colored red by
//    each shape's own mean expression.
// 3. Any other gene falls back to the original behavior: recolor the
//    existing cluster shapes by that gene's per-neighborhood mean
//    expression (`expression/<gene>.parquet`, cheap for any gene since it's
//    just a mean, not a real alpha shape). Expression stays per-neighborhood
//    (one slice, one cluster) even though cluster selection is cluster-wide,
//    so a gene's coloring genuinely varies across slices for the same
//    cluster.
//
// Either way, selecting a gene always clears any active cluster selection
// and its cell centroids -- gene view is tissue-wide, not filtered to (or
// occluded from above by) one cluster's cells.
export const select_nbhd_cloud_gene = async (gene, viz_state, layers_obj) => {
  const { nbhd_cloud } = viz_state;
  const isReset = gene === nbhd_cloud.selected_gene;

  if (isReset) {
    nbhd_cloud.selected_gene = null;
    nbhd_cloud.gene_stats = null;
    nbhd_cloud.selected_gene_max_mean = 0;
    if (nbhd_cloud.gene_shapes_mode) {
      nbhd_cloud.gene_shapes_mode = false;
      nbhd_cloud.gene_shapes_max_mean = 0;
      restore_cluster_shapes_data(viz_state, layers_obj);
    }
  } else if (nbhd_cloud.available_gene_shapes?.has(gene)) {
    nbhd_cloud.gene_shapes_cache ??= new Map();
    let features = nbhd_cloud.gene_shapes_cache.get(gene);
    if (!features) {
      const table = await get_arrow_table(
        `${viz_state.global_base_url}/nbhd_cloud/gene_shapes/${gene}.parquet`,
        options.fetch,
        viz_state.aws ?? null
      );
      features = parse_gene_shapes_table_to_features(table);
      nbhd_cloud.gene_shapes_cache.set(gene, features);
    }

    nbhd_cloud.selected_gene = gene;
    nbhd_cloud.gene_stats = null;
    nbhd_cloud.gene_shapes_mode = true;
    // Max across every slice's shape for this gene -- same tissue-wide
    // normalization principle as the recolor path below.
    nbhd_cloud.gene_shapes_max_mean = Math.max(
      0,
      ...features.map((feature) => feature.properties.mean_expression ?? 0)
    );
    update_nbhd_cloud_shapes_data(layers_obj, features);
  } else {
    if (nbhd_cloud.gene_shapes_mode) {
      nbhd_cloud.gene_shapes_mode = false;
      nbhd_cloud.gene_shapes_max_mean = 0;
      restore_cluster_shapes_data(viz_state, layers_obj);
    }

    nbhd_cloud.gene_expression_cache ??= new Map();
    let statsMap = nbhd_cloud.gene_expression_cache.get(gene);
    if (!statsMap) {
      const table = await get_arrow_table(
        `${viz_state.global_base_url}/nbhd_cloud/expression/${gene}.parquet`,
        options.fetch,
        viz_state.aws ?? null
      );
      statsMap = parse_gene_expression_table(table);
      nbhd_cloud.gene_expression_cache.set(gene, statsMap);
    }

    nbhd_cloud.selected_gene = gene;
    nbhd_cloud.gene_stats = statsMap;
    // The max is taken across every neighborhood in `statsMap` -- every
    // slice's instance of every cluster, since `expression/<gene>.parquet`
    // covers the whole tissue for this gene, not just one slice or cluster.
    // That's what makes alpha comparable across slices: two neighborhoods
    // with the same raw mean get the same alpha regardless of which slice
    // either one is in.
    nbhd_cloud.selected_gene_max_mean = Math.max(
      0,
      ...Array.from(statsMap.values(), (stats) => stats.mean)
    );
  }

  nbhd_cloud.selected_cluster_ids?.clear();
  await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

  update_nbhd_cloud_shapes_fill_color(layers_obj, viz_state);
};

// Backs the reused NBHD slider's is_nbhd_cloud branch (sliders.js) -- a
// manual 0-1 multiplier applied on top of the base fill alpha, so sliding it
// to 0 hides shapes and 100% (the default) is a no-op.
export const update_nbhd_cloud_manual_fill_opacity = (
  viz_state,
  layers_obj,
  manualOpacity
) => {
  viz_state.nbhd_cloud.manual_fill_opacity = manualOpacity;
  update_nbhd_cloud_shapes_fill_color(layers_obj, viz_state);
};

export const toggle_nbhd_cloud_shapes_layer_visibility = (
  layers_obj,
  visible
) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      visible,
    }
  );
};
