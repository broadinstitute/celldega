import { refresh_nbhd_cloud_cluster_cells } from '../deck-gl/layers/nbhd_cloud_cell_layer';
import {
  select_nbhd_cloud_gene,
  set_nbhd_cloud_cluster_selection,
} from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { update_selected_genes } from '../global_variables/selected_genes';
import { sync_nbhd_cloud_opacity_sliders } from '../ui/bar_plot';
import { refresh_layer } from '../utils/refresh_layer';

/**
 * Select one or more neighborhood-cloud clusters the same way clicking a
 * bar/shape (single cluster) or cutting a Clustergram column dendrogram
 * (a "meta-cluster" grouping several clusters at once) does -- mirrors
 * bar_plot.js's bar_callback_nbhd_cloud_cluster and
 * nbhd_cloud_shapes_layer.js's onClick handler. Used when the selection
 * instead arrives from a linked Clustergram's `update_trigger`.
 * `update_ist_landscape_from_cgm`'s generic cell-cluster path only ever
 * refreshes the shared (inert, for this technology) `cell_layer`, so a
 * Clustergram-driven cluster click never reached the real
 * `nbhd_cloud_shapes_layer` / `nbhd_cloud_cell_layer` without this.
 */
export const select_nbhd_cloud_clusters_from_link = async (
  clusterIds,
  viz_state,
  layers_obj
) => {
  const idStrings = clusterIds.map(String);
  set_nbhd_cloud_cluster_selection(idStrings, viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
  sync_nbhd_cloud_opacity_sliders(viz_state);

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
  viz_state.genes.svg_bar_gene?.selectAll('rect').style('opacity', 1.0);

  await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_cell_layer');
};

/** Single-cluster convenience wrapper around
 * select_nbhd_cloud_clusters_from_link, for the plain (non-dendrogram)
 * row_label/col_label click branches. */
export const select_nbhd_cloud_cluster_from_link = async (
  clusterId,
  viz_state,
  layers_obj
) => select_nbhd_cloud_clusters_from_link([clusterId], viz_state, layers_obj);

/**
 * Select a neighborhood-cloud gene the same way clicking its bar does
 * (mirrors bar_plot.js's bar_callback_gene nbhd_cloud branch) -- used when
 * the selection instead arrives from a linked Clustergram's
 * `update_trigger`. Same rationale as
 * :func:`select_nbhd_cloud_cluster_from_link` above: the generic gene path
 * only touches the shared per-cell gene machinery
 * (`update_cell_exp_array` / `cell_layer`), which neighborhood-cloud never
 * populates -- real gene coloring lives entirely in
 * `nbhd_cloud_shapes_layer` / `nbhd_cloud_cell_layer`.
 */
export const select_nbhd_cloud_gene_from_link = async (
  gene,
  viz_state,
  layers_obj
) => {
  const isReset = gene === viz_state.nbhd_cloud.selected_gene;
  await select_nbhd_cloud_gene(gene, viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_cell_layer');
  sync_nbhd_cloud_opacity_sliders(viz_state);

  // A gene with neither a shape nor a cell scatter is a no-op
  // (select_nbhd_cloud_gene leaves state untouched) -- don't relabel bars
  // for a click that didn't actually do anything.
  const isAvailable =
    viz_state.nbhd_cloud.available_gene_shapes?.has(gene) ||
    viz_state.nbhd_cloud.available_gene_scatter?.has(gene);
  if (!isReset && !isAvailable) {
    return;
  }

  // Drives the Uniprot gene-info panel (ui_containers.js's
  // obs_store.selected_genes subscriber), same as the bar/search paths.
  update_selected_genes(
    viz_state.genes,
    isReset ? [] : [gene],
    viz_state.obs_store
  );

  const hasSelection = viz_state.nbhd_cloud.selected_gene != null;
  viz_state.genes.svg_bar_gene
    ?.selectAll('rect')
    .style('opacity', (bar) =>
      !hasSelection || bar.name === viz_state.nbhd_cloud.selected_gene
        ? 1.0
        : 0.2
    );
  viz_state.nbhd_cloud.svg_bar_cluster?.selectAll('rect').style('opacity', 1.0);
};
