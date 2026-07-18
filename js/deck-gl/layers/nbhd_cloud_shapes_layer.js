import { GeoJsonLayer } from 'deck.gl';

import { options } from '../../global_variables/fetch_options';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import { parse_gene_expression_table } from '../../read_parquet/nbhd_cloud_tables';
import { hexToRgb } from '../../utils/hexToRgb';
import { getModelMatrixProps } from '../../utils/rotation';

// Reuses the same red-hue, alpha-encodes-expression convention already used
// for per-cell gene coloring (cell_color.js) rather than a separate
// colormap, so a neighborhood doesn't visually change representation when it
// crossfades into cells at the same zoom level.
const GENE_COLOR_RGB = [255, 0, 0];

export const is_nbhd_cloud_gene_color_mode = (nbhd_cloud) =>
  nbhd_cloud?.selected_gene != null;

// `fillOpacityFraction` is the zoom-driven crossfade fraction (1 = fully
// opaque "shapes" tier, 0 = fully faded into cells) — gene-mode alpha is the
// product of that fraction and the expression-driven alpha, so gene
// coloring still respects the ambient crossfade instead of overriding it.
export const get_nbhd_cloud_fill_color = (
  feature,
  viz_state,
  fillOpacityFraction
) => {
  const { nbhd_cloud } = viz_state;

  // A neighborhood the user explicitly selected (nbhd bar / shape click)
  // stays fully opaque regardless of the ambient zoom-driven fade — a
  // bounded, explicit override that composes with (doesn't replace) the
  // continuous crossfade.
  const isSelected = nbhd_cloud.selected_neighborhood_ids?.has(
    feature.properties.neighborhood_id
  );
  const effectiveFraction = isSelected ? 1 : fillOpacityFraction;

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

export const ini_nbhd_cloud_shapes_layer = (viz_state, features = []) => {
  return new GeoJsonLayer({
    id: 'nbhd-cloud-shapes-layer',
    data: { type: 'FeatureCollection', features },
    pickable: true,
    stroked: true,
    filled: true,
    getLineWidth: 1,
    lineWidthMinPixels: 1,
    getFillColor: (d) => get_nbhd_cloud_fill_color(d, viz_state, 1),
    getLineColor: (d) => [...hexToRgb(d.properties.color), 255],
    opacity: 1,
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

// Drives the crossfade (§ nbhd_cloud_lod.js) and, when a gene is selected,
// the expression-driven alpha — both live in the same accessor since the
// spec calls for gene alpha to be multiplied by the ambient fade fraction,
// not to replace it.
export const update_nbhd_cloud_shapes_fill_opacity = (
  layers_obj,
  viz_state,
  fillOpacityFraction
) => {
  layers_obj.nbhd_cloud_shapes_layer = layers_obj.nbhd_cloud_shapes_layer.clone(
    {
      getFillColor: (d) =>
        get_nbhd_cloud_fill_color(d, viz_state, fillOpacityFraction),
      updateTriggers: {
        getFillColor: [fillOpacityFraction, viz_state.nbhd_cloud.selected_gene],
      },
    }
  );
};

// Toggles a single neighborhood's "revealed" state (nbhd bar click, or a
// future shape click) — bounded to one neighborhood, additive to the
// zoom-driven crossfade rather than a mode switch.
export const toggle_nbhd_cloud_neighborhood_selection = (
  neighborhoodId,
  viz_state,
  layers_obj
) => {
  const { nbhd_cloud } = viz_state;
  nbhd_cloud.selected_neighborhood_ids ??= new Set();

  if (nbhd_cloud.selected_neighborhood_ids.has(neighborhoodId)) {
    nbhd_cloud.selected_neighborhood_ids.delete(neighborhoodId);
  } else {
    nbhd_cloud.selected_neighborhood_ids.add(neighborhoodId);
  }

  update_nbhd_cloud_shapes_fill_opacity(
    layers_obj,
    viz_state,
    nbhd_cloud.last_fill_opacity ?? 1
  );
};

// Toggles gene-based neighborhood coloring on/off, mirroring the cell-level
// cluster-vs-gene toggle (cell_color.js's `cats.cat`) but scoped to
// `viz_state.nbhd_cloud` — clicking the same gene bar again reverts to
// cluster color, same as the existing gene bar click behavior elsewhere.
// `expression/<gene>.parquet` is fetched lazily (once per gene, cached) only
// when that gene is actually selected.
export const select_nbhd_cloud_gene = async (gene, viz_state, layers_obj) => {
  const { nbhd_cloud } = viz_state;
  const isReset = gene === nbhd_cloud.selected_gene;

  if (isReset) {
    nbhd_cloud.selected_gene = null;
    nbhd_cloud.gene_stats = null;
    nbhd_cloud.selected_gene_max_mean = 0;
  } else {
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
    nbhd_cloud.selected_gene_max_mean = Math.max(
      0,
      ...Array.from(statsMap.values(), (stats) => stats.mean)
    );
  }

  update_nbhd_cloud_shapes_fill_opacity(
    layers_obj,
    viz_state,
    nbhd_cloud.last_fill_opacity ?? 1
  );
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
