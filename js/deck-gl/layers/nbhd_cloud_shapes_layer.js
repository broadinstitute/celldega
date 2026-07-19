import { GeoJsonLayer } from 'deck.gl';

import { toExpressionByte } from '../../global_variables/cell_exp_array';
import { options } from '../../global_variables/fetch_options';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import { parse_gene_shapes_table_to_features } from '../../read_parquet/nbhd_cloud_tables';
import { hexToRgb } from '../../utils/hexToRgb';
import { refresh_layer } from '../../utils/refresh_layer';
import { getModelMatrixProps } from '../../utils/rotation';

import {
  refresh_nbhd_cloud_cluster_cells,
  update_nbhd_cloud_cell_layer_opacity,
} from './nbhd_cloud_cell_layer';

// Reuses the same red hue already used for per-cell gene coloring
// (cell_color.js) rather than a separate colormap.
const GENE_COLOR_RGB = [255, 0, 0];

// Shared between the initial gene-bar build (ui_containers.js) and the
// viewport-driven gene-bar republish (calc_viewport.js's
// getPointCloudGeneBars) -- both target the same `svg_bar_gene`, so both
// need to agree on "the curated gene-shapes list" as the bar data for
// neighborhood-cloud, or the viewport publisher would silently overwrite
// the curated bars with the generic top-gene panel on the first pan/zoom.
export const build_nbhd_cloud_gene_bar_data = (nbhd_cloud) =>
  [...(nbhd_cloud?.available_gene_shapes ?? new Map())].map(
    ([gene, maxExpression]) => ({
      name: gene,
      value: maxExpression,
    })
  );

// Applied to every shape outside the selected cluster (bar click or direct
// shape click) when a selection is active -- fully transparent, not just
// dimmed, so only the selected cluster's shapes are visible.
const UNSELECTED_DIM_FACTOR = 0;

// The manifest of genes with precomputed alpha shapes (a small curated
// marker-gene list, see write_gene_shapes) -- `{gene: max_expression}`,
// where max_expression is that gene's whole-tissue single-cell max, used to
// normalize fill opacity (mirroring the per-cell gene-coloring convention).
// Missing for most datasets -- that's the normal case, not an error, so this
// resolves to an empty Map rather than throwing on a 404/network failure.
export const fetch_available_gene_shapes = async (base_url, aws) => {
  const url = `${base_url}/nbhd_cloud/shapes/by_gene/available_genes.json`;
  try {
    const response = aws
      ? await aws.fetch(url)
      : await fetch(url, options.fetch);
    if (!response.ok) {
      return new Map();
    }
    const genes = await response.json();
    return new Map(Object.entries(genes));
  } catch {
    return new Map();
  }
};

export const get_nbhd_cloud_fill_color = (feature, viz_state) => {
  const { nbhd_cloud } = viz_state;

  // Gene-shapes mode: a different feature set entirely (one polygon per
  // (slice, gene) from a curated marker-gene list, see write_gene_shapes),
  // each carrying its own `mean_expression` directly -- no cluster_id, no
  // cluster-selection dimming (there's no cluster concept here to dim
  // against). Opacity is its own independent slider (the repurposed TRX
  // slider, sliders.js), not the cluster-mode one.
  if (nbhd_cloud.gene_shapes_mode) {
    const maxExpression =
      nbhd_cloud.available_gene_shapes?.get(feature.properties.gene) ?? 0;
    const baseAlpha = toExpressionByte(
      feature.properties.mean_expression ?? 0,
      maxExpression
    );
    const alpha = Math.round(baseAlpha * (nbhd_cloud.gene_fill_opacity ?? 1));
    return [...GENE_COLOR_RGB, alpha];
  }

  const clusterId = String(feature.properties.cluster_id);
  const hasSelection = (nbhd_cloud.selected_cluster_ids?.size ?? 0) > 0;
  const isSelected = nbhd_cloud.selected_cluster_ids?.has(clusterId);
  const selectionFactor =
    !hasSelection || isSelected ? 1 : UNSELECTED_DIM_FACTOR;
  const effectiveFraction =
    (nbhd_cloud.manual_fill_opacity ?? 1) * selectionFactor;

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

export const update_nbhd_cloud_shapes_data = (layers_obj, features) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      data: { type: 'FeatureCollection', features },
    }
  );
};

// The feature set the SLICE bar's isolate filter should apply to: the
// current gene's own shapes while gene-shapes mode is active, otherwise the
// cluster shapes. Getting this wrong is exactly the "isolate a slice while
// viewing a gene" statefulness bug -- filtering the wrong feature set (or
// filtering cluster shapes while `gene_shapes_mode` stays stuck on) leaves
// the displayed data and the mode flag disagreeing about what's shown.
const get_current_base_features = (viz_state) => {
  const { nbhd_cloud } = viz_state;
  if (nbhd_cloud.gene_shapes_mode && nbhd_cloud.selected_gene) {
    return nbhd_cloud.gene_shapes_cache?.get(nbhd_cloud.selected_gene) ?? [];
  }
  return nbhd_cloud.shapes_features;
};

const get_slice_filtered_features = (viz_state, baseFeatures) => {
  const { nbhd_cloud } = viz_state;
  const hasSliceSelection = (nbhd_cloud.selected_slice_ids?.size ?? 0) > 0;
  return hasSliceSelection
    ? baseFeatures.filter((feature) =>
        nbhd_cloud.selected_slice_ids.has(feature.properties.slice_id)
      )
    : baseFeatures;
};

// Backs the SLICE bar's isolate behavior (bar_plot.js) -- applies (or
// re-applies) the current slice selection to whichever feature set is
// currently relevant (cluster shapes, or the selected gene's shapes),
// swapping the rendered set rather than dimming so an unselected slice's
// shapes are genuinely gone.
export const apply_nbhd_cloud_slice_filter = (viz_state, layers_obj) => {
  const baseFeatures = get_current_base_features(viz_state);
  update_nbhd_cloud_shapes_data(
    layers_obj,
    get_slice_filtered_features(viz_state, baseFeatures)
  );
};

// Restores the shapes layer to the cluster-based shapes (respecting any
// active slice isolation) -- called whenever gene-shapes mode is exited,
// since that mode swapped `data` to a wholly different feature set (one
// polygon per (slice, gene) instead of per (slice, cluster)).
const restore_cluster_shapes_data = (viz_state, layers_obj) => {
  update_nbhd_cloud_shapes_data(
    layers_obj,
    get_slice_filtered_features(viz_state, viz_state.nbhd_cloud.shapes_features)
  );
};

export const update_nbhd_cloud_shapes_fill_color = (layers_obj, viz_state) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      getFillColor: (d) => get_nbhd_cloud_fill_color(d, viz_state),
      updateTriggers: {
        getFillColor: [
          viz_state.nbhd_cloud.selected_gene,
          viz_state.nbhd_cloud.gene_shapes_mode,
          viz_state.nbhd_cloud.gene_fill_opacity,
          viz_state.nbhd_cloud.manual_fill_opacity,
          // Not just `.size` -- switching from cluster A to cluster B is a
          // same-size (1 -> 1) change that `.size` can't see, so deck.gl
          // would never recompute colors and the newly selected cluster's
          // shape would silently keep rendering as "not selected" (dimmed).
          [...(viz_state.nbhd_cloud.selected_cluster_ids ?? [])].join(','),
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
// Cluster selection and gene-shapes mode are mutually exclusive -- picking a
// cluster always reverts to cluster-color highlighting, clearing whatever
// gene was selected (the bar's own opacity reset happens at the call sites,
// which also own the gene bar's DOM).
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

  if (nbhd_cloud.gene_shapes_mode) {
    nbhd_cloud.gene_shapes_mode = false;
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

  // NBHD/TRX slider cross-disable (sliders.js owns the full toggle_slider
  // helper, but importing it here would be circular -- sliders.js already
  // imports from this module). Cluster selection always ends in
  // cluster-color mode, so NBHD enabled / TRX disabled.
  if (viz_state.sliders?.nbhd) {
    viz_state.sliders.nbhd.disabled = false;
  }
  if (viz_state.sliders?.trx) {
    viz_state.sliders.trx.disabled = true;
  }
};

export const set_nbhd_cloud_shapes_layer_onclick = (layers_obj, viz_state) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      onClick: (info, event) =>
        nbhd_cloud_shapes_onclick(info, event, layers_obj, viz_state),
    }
  );
};

// Backs the gene bar's click (and gene search) -- a gene either has
// precomputed alpha shapes (the small curated marker-gene list from
// write_gene_shapes) or it doesn't; there's no per-neighborhood mean
// recolor fallback for the rest of the gene panel (that data isn't computed
// or written anymore -- it was dead weight once gene-shapes worked, since
// nothing else read it). Selecting an unavailable gene is a no-op: nothing
// fetched, nothing changed.
//
// Selecting a gene-shapes gene always clears any active cluster selection
// and its cell centroids -- gene view is tissue-wide, not filtered to (or
// occluded from above by) one cluster's cells.
export const select_nbhd_cloud_gene = async (gene, viz_state, layers_obj) => {
  const { nbhd_cloud } = viz_state;
  const isReset = gene === nbhd_cloud.selected_gene;

  if (isReset) {
    nbhd_cloud.selected_gene = null;
    nbhd_cloud.gene_shapes_mode = false;
    restore_cluster_shapes_data(viz_state, layers_obj);
  } else if (nbhd_cloud.available_gene_shapes?.has(gene)) {
    nbhd_cloud.gene_shapes_cache ??= new Map();
    let features = nbhd_cloud.gene_shapes_cache.get(gene);
    if (!features) {
      const table = await get_arrow_table(
        `${viz_state.global_base_url}/nbhd_cloud/shapes/by_gene/${gene}.parquet`,
        options.fetch,
        viz_state.aws ?? null
      );
      features = parse_gene_shapes_table_to_features(table);
      nbhd_cloud.gene_shapes_cache.set(gene, features);
    }

    nbhd_cloud.selected_gene = gene;
    nbhd_cloud.gene_shapes_mode = true;
    apply_nbhd_cloud_slice_filter(viz_state, layers_obj);
  } else {
    // No precomputed shapes for this gene -- nothing to show, so leave
    // whatever was already displayed alone rather than clearing a valid
    // selection out from under the user.
    return;
  }

  nbhd_cloud.selected_cluster_ids?.clear();
  await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);

  update_nbhd_cloud_shapes_fill_color(layers_obj, viz_state);
};

// Backs the reused NBHD slider's is_nbhd_cloud branch (sliders.js) -- a
// manual 0-1 multiplier applied on top of the base fill alpha for
// cluster-color mode. Disabled (sliders.js) while gene-shapes mode is
// active, since that mode has its own independent opacity control below.
// Also drives cell centroid opacity, since centroids sit on top of the
// shape they belong to and should dim/brighten together with it.
export const update_nbhd_cloud_manual_fill_opacity = (
  viz_state,
  layers_obj,
  manualOpacity
) => {
  viz_state.nbhd_cloud.manual_fill_opacity = manualOpacity;
  update_nbhd_cloud_shapes_fill_color(layers_obj, viz_state);
  update_nbhd_cloud_cell_layer_opacity(layers_obj, viz_state);
};

// Backs the repurposed TRX slider (sliders.js) -- an independent 0-1
// multiplier for gene-shapes mode's fill opacity, so cluster-color and
// gene-shapes opacity can be tuned separately rather than sharing one
// slider whose meaning changes depending on mode.
export const update_nbhd_cloud_gene_fill_opacity = (
  viz_state,
  layers_obj,
  opacity
) => {
  viz_state.nbhd_cloud.gene_fill_opacity = opacity;
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
