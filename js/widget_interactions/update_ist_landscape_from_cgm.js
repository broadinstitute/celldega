import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { refresh_layer } from '../utils/refresh_layer';

import {
  select_nbhd_cloud_cluster_from_link,
  select_nbhd_cloud_clusters_from_link,
  select_nbhd_cloud_gene_from_link,
} from './nbhd_cloud_link';

/**
 * Strip cell name prefix if cell_name_prefix is enabled.
 * When cell_name_prefix is true, cell names have format "prefix_name"
 * and we need to strip the prefix to match Landscape cell names.
 */
const strip_cell_prefix = (name, viz_state) => {
  if (!viz_state.cell_name_prefix) return name;
  if (typeof name !== 'string') return name;
  const idx = name.indexOf('_');
  return idx >= 0 ? name.substring(idx + 1) : name;
};

/**
 * Strip prefixes from an array of cell names.
 */
const strip_cell_prefixes = (names, viz_state) => {
  if (!viz_state.cell_name_prefix) return names;
  return names.map((n) => strip_cell_prefix(n, viz_state));
};

/**
 * Helper to clear cell selection and reset to cluster mode.
 */
const reset_to_cluster_mode = (viz_state, layers_obj) => {
  viz_state.highlighted_cells = new Set();
  viz_state.obs_store.selected_cells.set([]);
  update_cat(viz_state.cats, 'cluster');
  update_selected_cats(viz_state.cats, [], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);
  viz_state.obs_store.viz_nbhd_layer.set(false);
  viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');
  refresh_layer(viz_state, layers_obj, 'cell_layer');
};

/**
 * Check if a click value represents a cell cluster selection.
 * Supports both legacy format (row_entity === 'cell_cluster') and
 * new format (entity === 'cell' && attr === 'leiden').
 */
export const is_cell_cluster = (clickValue) => {
  if (!clickValue) return false;

  // Legacy format check
  if (clickValue.row_entity === 'cell_cluster') return true;

  // New format check: entity is 'cell' and attr is a clustering attribute
  if (clickValue.entity === 'cell') {
    const clusteringAttrs = ['leiden', 'cluster', 'cell_type', 'cell_cluster'];
    return clusteringAttrs.includes(clickValue.attr);
  }

  return false;
};

/**
 * Check if a click value represents a neighborhood selection.
 */
export const is_neighborhood = (clickValue) => {
  if (!clickValue) return false;

  // Legacy format check
  if (clickValue.col_entity === 'nbhd') return true;

  // New format check
  return clickValue.entity === 'nbhd' || clickValue.entity === 'hextile';
};

/**
 * Check if a click value represents a gene selection.
 */
export const is_gene = (clickValue) => {
  if (!clickValue) return false;

  // New format check
  return clickValue.entity === 'gene';
};

/**
 * Check if a click value represents an individual cell selection.
 * This is when entity is 'cell' and attr is 'name' (not a cluster attribute).
 */
export const is_cell = (clickValue) => {
  if (!clickValue) return false;

  // Check for cell entity with name attribute (individual cells)
  return clickValue.entity === 'cell' && clickValue.attr === 'name';
};

export const update_ist_landscape_from_cgm = async (
  deck_ist,
  layers_obj,
  viz_state
) => {
  const raw_click = viz_state.model.get('update_trigger');
  if (!raw_click || typeof raw_click !== 'object') {
    return;
  }

  const click_info = {
    type: raw_click.type || raw_click.click_type,
    value: raw_click.value || raw_click.click_value,
  };

  const click_type = click_info.type?.replace('-', '_');

  if (!click_type) {
    return;
  }

  let inst_gene;
  let new_cat;

  // add try catch block
  try {
    if (click_type === 'row_label') {
      // Check if this is a neighborhood selection
      if (is_neighborhood(click_info.value)) {
        const new_nbhd = click_info.value.name;
        const prev_selected = viz_state.obs_store.selected_nbhds.get();

        // Toggle: if clicking the same nbhd, deselect it
        const is_same =
          prev_selected.length === 1 && prev_selected[0] === new_nbhd;

        if (is_same) {
          // Deselect - show all nbhds
          viz_state.obs_store.selected_nbhds.set([]);
          viz_state.nbhd?.svg_bar_nbhd?.selectAll('rect').style('opacity', 1.0);
        } else {
          // Select the new nbhd
          viz_state.obs_store.selected_nbhds.set([new_nbhd]);
          viz_state.nbhd?.svg_bar_nbhd
            ?.selectAll('rect')
            .style('opacity', (d) => (d.name === new_nbhd ? 1.0 : 0.2));

          viz_state.nbhd?.svg_bar_nbhd
            ?.selectAll('rect')
            .filter((d) => d.name === new_nbhd)
            .node()
            ?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            });
        }

        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      } else if (is_cell_cluster(click_info.value)) {
        // Cell cluster selection
        inst_gene = 'cluster';
        new_cat = click_info.value.name;

        if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
          // neighborhood-cloud's cluster coloring lives in a dedicated pair
          // of layers (nbhd_cloud_shapes_layer / nbhd_cloud_cell_layer),
          // not the generic (inert, for this technology) cell_layer path
          // below -- see select_nbhd_cloud_cluster_from_link.
          await select_nbhd_cloud_cluster_from_link(
            new_cat,
            viz_state,
            layers_obj
          );
        } else {
          // Clear selected cells when switching to cluster mode
          viz_state.obs_store.selected_cells.set([]);

          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
          update_selected_genes(viz_state.genes, [], viz_state.obs_store);

          viz_state.obs_store.viz_nbhd_layer.set(false);
          viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

          refresh_layer(viz_state, layers_obj, 'cell_layer');
        }
      } else {
        // Treat as gene selection
        inst_gene = click_info.value.name;

        if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
          // neighborhood-cloud's gene coloring lives in a dedicated pair of
          // layers (nbhd_cloud_shapes_layer / nbhd_cloud_cell_layer), not
          // the generic per-cell path below -- see
          // select_nbhd_cloud_gene_from_link.
          await select_nbhd_cloud_gene_from_link(
            inst_gene,
            viz_state,
            layers_obj
          );
        } else {
          new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

          // Clear highlighted cells immediately (without triggering subscription refresh)
          // This prevents the old gene data from showing during loading
          viz_state.highlighted_cells = new Set();

          update_cat(viz_state.cats, new_cat);
          update_selected_genes(
            viz_state.genes,
            [inst_gene],
            viz_state.obs_store
          );

          // Load gene expression data BEFORE updating selected_cats
          // This ensures cell_exp_array is populated before the cell layer refreshes
          await update_cell_exp_array(
            viz_state.cats,
            viz_state.genes,
            viz_state.global_base_url,
            inst_gene,
            viz_state.seg.version,
            viz_state.vector_name_integer,
            viz_state.aws,
            viz_state.row_group_readers?.cbg
          );

          // Clear selected cells in obs_store (after data is loaded to avoid flash)
          viz_state.obs_store.selected_cells.set([]);

          // Update selected_cats after cell_exp_array has been populated
          update_selected_cats(
            viz_state.cats,
            new_cat === 'cluster' ? [] : [inst_gene],
            viz_state.obs_store
          );

          viz_state.obs_store.viz_nbhd_layer.set(false);
          viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'trx_layer');
        }
      }
    } else if (click_type === 'col_label') {
      // Check if this is a neighborhood selection
      if (is_neighborhood(click_info.value)) {
        const new_nbhd = click_info.value.name;
        const prev_selected = viz_state.obs_store.selected_nbhds.get();

        // Toggle: if clicking the same nbhd, deselect it
        const is_same =
          prev_selected.length === 1 && prev_selected[0] === new_nbhd;

        if (is_same) {
          // Deselect - show all nbhds
          viz_state.obs_store.selected_nbhds.set([]);
          viz_state.nbhd?.svg_bar_nbhd?.selectAll('rect').style('opacity', 1.0);
        } else {
          // Select the new nbhd
          viz_state.obs_store.selected_nbhds.set([new_nbhd]);
          viz_state.nbhd?.svg_bar_nbhd
            ?.selectAll('rect')
            .style('opacity', (d) => (d.name === new_nbhd ? 1.0 : 0.2));

          viz_state.nbhd?.svg_bar_nbhd
            ?.selectAll('rect')
            .filter((d) => d.name === new_nbhd)
            .node()
            ?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            });
        }

        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      } else if (is_cell(click_info.value)) {
        // Individual cell selection - highlight in landscape
        const cell_name = strip_cell_prefix(click_info.value.name, viz_state);
        viz_state.obs_store.selected_cells.set([cell_name]);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else {
        inst_gene = 'cluster';
        new_cat = click_info.value.name;

        if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
          await select_nbhd_cloud_cluster_from_link(
            new_cat,
            viz_state,
            layers_obj
          );
        } else {
          // Clear selected cells when switching to cluster mode
          viz_state.obs_store.selected_cells.set([]);

          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
          update_selected_genes(viz_state.genes, [], viz_state.obs_store);

          viz_state.obs_store.viz_nbhd_layer.set(false);
          viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'nbhd_layer');
          refresh_layer(viz_state, layers_obj, 'trx_layer');
        }
      }
    } else if (click_type === 'col_dendro') {
      const new_cats = click_info.value.selected_names || [];
      const is_unselecting =
        click_info.value.is_unselecting || new_cats.length === 0;

      // Handle unselection - clear all states and return to cluster mode
      if (is_unselecting) {
        viz_state.obs_store.selected_nbhds.set([]);
        viz_state.nbhd?.svg_bar_nbhd?.selectAll('rect').style('opacity', 1.0);
        reset_to_cluster_mode(viz_state, layers_obj);
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        return;
      }

      // Check if columns represent neighborhoods
      const col_entity_full =
        click_info.value.col_entity_full || click_info.value;
      if (is_neighborhood(col_entity_full)) {
        viz_state.obs_store.selected_nbhds.set(new_cats);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          const selected_nbhds = viz_state.obs_store.selected_nbhds.get();
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) =>
              selected_nbhds.includes(d.name) ? 1.0 : 0.2
            );

          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .filter((d) => selected_nbhds.includes(d.name))
            .node()
            ?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            });
        } else {
          viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
        }
      } else if (is_cell(col_entity_full)) {
        // Individual cells selected via dendrogram - highlight in landscape
        const stripped_cells = strip_cell_prefixes(new_cats, viz_state);
        viz_state.obs_store.selected_cells.set(stripped_cells);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
        // A dendrogram cut selecting more than one cluster column is a
        // "meta-cluster" -- every cluster in the cut stays selected at once
        // (see select_nbhd_cloud_clusters_from_link).
        await select_nbhd_cloud_clusters_from_link(
          new_cats,
          viz_state,
          layers_obj
        );
      } else {
        // Clear selected cells when switching to cluster mode
        viz_state.obs_store.selected_cells.set([]);

        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      }
    } else if (click_type === 'row_dendro') {
      const new_cats = click_info.value.selected_names || [];
      const is_unselecting =
        click_info.value.is_unselecting || new_cats.length === 0;

      // Handle unselection - clear all states and return to cluster mode
      if (is_unselecting) {
        viz_state.obs_store.selected_nbhds.set([]);
        viz_state.nbhd?.svg_bar_nbhd?.selectAll('rect').style('opacity', 1.0);
        reset_to_cluster_mode(viz_state, layers_obj);
        refresh_layer(viz_state, layers_obj, 'trx_layer');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        return;
      }

      // Check if rows represent neighborhoods
      const row_entity_full =
        click_info.value.row_entity_full || click_info.value;
      if (is_neighborhood(row_entity_full)) {
        // Neighborhood selection from row dendrogram
        viz_state.obs_store.selected_nbhds.set(new_cats);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'cell_layer');

        if (viz_state.nbhd?.svg_bar_nbhd) {
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) => (new_cats.includes(d.name) ? 1.0 : 0.2));
        }
      } else if (is_cell_cluster(row_entity_full)) {
        if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
          // "Meta-cluster" selection -- see the col_dendro branch above.
          await select_nbhd_cloud_clusters_from_link(
            new_cats,
            viz_state,
            layers_obj
          );
          return;
        }
        viz_state.highlighted_cells = new Set();
        viz_state.obs_store.selected_cells.set([]);
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);
        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
      } else if (is_gene(row_entity_full)) {
        // Gene selection from row dendrogram
        // Note: Don't use update_selected_genes here as it has toggle behavior
        // that conflicts with Clustergram's own sync. Instead, just set the genes
        // directly for visualization purposes. The Clustergram handles syncing
        // selected_genes to Python.
        viz_state.genes.selected_genes = new_cats;
        viz_state.obs_store.selected_genes.set(new_cats);

        if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
          // Only one gene can be selected at a time in neighborhood-cloud
          // (see select_nbhd_cloud_gene_from_link) -- a dendrogram cut
          // selecting more than one gene has no single-gene equivalent.
          if (new_cats.length === 1) {
            await select_nbhd_cloud_gene_from_link(
              new_cats[0],
              viz_state,
              layers_obj
            );
          }
          return;
        }

        if (new_cats.length === 1) {
          inst_gene = new_cats[0];
          new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

          // Clear highlighted cells immediately (without triggering subscription refresh)
          viz_state.highlighted_cells = new Set();

          update_cat(viz_state.cats, new_cat);

          // Load gene expression data BEFORE updating selected_cats
          await update_cell_exp_array(
            viz_state.cats,
            viz_state.genes,
            viz_state.global_base_url,
            inst_gene,
            viz_state.seg.version,
            viz_state.vector_name_integer,
            viz_state.aws
          );

          // Clear selected cells in obs_store (after data is loaded)
          viz_state.obs_store.selected_cells.set([]);

          // Update selected_cats after cell_exp_array has been populated
          update_selected_cats(
            viz_state.cats,
            new_cat === 'cluster' ? [] : [inst_gene],
            viz_state.obs_store
          );
        } else {
          // Multiple genes selected - just switch to cluster mode for now
          viz_state.highlighted_cells = new Set();
          viz_state.obs_store.selected_cells.set([]);
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);
        }

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      }
    } else if (click_type === 'cat_value') {
      // Category bar/tile click - highlight cells in that category
      const {
        axis,
        attr_name: _attr_name,
        value,
        node_names,
      } = click_info.value;
      const { col_entity_full } = click_info.value;

      // If columns are cells and we clicked a category on the column axis
      if (axis === 'col' && is_cell(col_entity_full)) {
        // node_names contains all cells in this category - strip prefixes if needed
        const stripped_cells = strip_cell_prefixes(node_names || [], viz_state);
        viz_state.obs_store.selected_cells.set(stripped_cells);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else if (axis === 'col') {
        // Category on columns (e.g., cell clusters)
        // Clear selected cells when switching to cluster mode
        viz_state.obs_store.selected_cells.set([]);

        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [value], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      }
    } else if (click_type === 'mat_value') {
      const { row, col, row_entity_full, col_entity_full } = click_info.value;

      // Use the full entity info if available
      const rowEntity = row_entity_full || row;
      const colEntity = col_entity_full || col;

      // Helper to check if two entities match (same entity type and attribute)
      const entitiesMatch = (e1, e2) =>
        e1?.entity === e2?.entity && e1?.attr === e2?.attr;

      // Check if we have a cell cluster + neighborhood combination
      if (is_cell_cluster(rowEntity) && is_neighborhood(colEntity)) {
        const new_nbhds = [col.name];
        viz_state.obs_store.selected_nbhds.set(new_nbhds);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');

        // Also highlight the selected cluster
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [row.name], viz_state.obs_store);
        refresh_layer(viz_state, layers_obj, 'cell_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          const selected_nbhds = viz_state.obs_store.selected_nbhds.get();
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) =>
              selected_nbhds.includes(d.name) ? 1.0 : 0.2
            );
        }
      } else if (
        entitiesMatch(rowEntity, colEntity) &&
        is_cell_cluster(rowEntity)
      ) {
        // Same entity:attr on both axes (e.g., cluster-cluster similarity matrix)
        // Highlight BOTH clusters in the Landscape
        viz_state.obs_store.selected_cells.set([]);
        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        update_cat(viz_state.cats, 'cluster');
        // Select both the row and column clusters
        const selected_clusters = [row.name, col.name];
        update_selected_cats(
          viz_state.cats,
          selected_clusters,
          viz_state.obs_store
        );
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else if (is_gene(rowEntity) && is_cell_cluster(colEntity)) {
        // Gene (row) x Cluster (col): Show gene expression filtered to cluster
        const gene_name = row.name;
        const cluster_name = col.name;

        // Clear any previous cell selection
        viz_state.highlighted_cells = new Set();
        viz_state.obs_store.selected_cells.set([]);

        // Set the gene as the category for coloring
        update_cat(viz_state.cats, gene_name);
        update_selected_genes(
          viz_state.genes,
          [gene_name],
          viz_state.obs_store
        );

        // Load gene expression data
        await update_cell_exp_array(
          viz_state.cats,
          viz_state.genes,
          viz_state.global_base_url,
          gene_name,
          viz_state.seg.version,
          viz_state.vector_name_integer,
          viz_state.aws
        );

        // Update selected_cats to filter to only cells in this cluster
        // The cell layer will use this to filter which cells to show
        update_selected_cats(
          viz_state.cats,
          [cluster_name],
          viz_state.obs_store
        );

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      } else if (is_cell_cluster(rowEntity) && is_gene(colEntity)) {
        // Cluster (row) x Gene (col): Show gene expression filtered to cluster
        const cluster_name = row.name;
        const gene_name = col.name;

        // Clear any previous cell selection
        viz_state.highlighted_cells = new Set();
        viz_state.obs_store.selected_cells.set([]);

        // Set the gene as the category for coloring
        update_cat(viz_state.cats, gene_name);
        update_selected_genes(
          viz_state.genes,
          [gene_name],
          viz_state.obs_store
        );

        // Load gene expression data
        await update_cell_exp_array(
          viz_state.cats,
          viz_state.genes,
          viz_state.global_base_url,
          gene_name,
          viz_state.seg.version,
          viz_state.vector_name_integer,
          viz_state.aws
        );

        // Update selected_cats to filter to only cells in this cluster
        update_selected_cats(
          viz_state.cats,
          [cluster_name],
          viz_state.obs_store
        );

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      } else if (is_neighborhood(rowEntity) && is_cell_cluster(colEntity)) {
        // Neighborhood (row) x Cluster (col): Highlight nbhd and cluster
        const new_nbhds = [row.name];
        viz_state.obs_store.selected_nbhds.set(new_nbhds);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');

        // Also highlight the selected cluster
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [col.name], viz_state.obs_store);
        refresh_layer(viz_state, layers_obj, 'cell_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          const selected_nbhds = viz_state.obs_store.selected_nbhds.get();
          viz_state.nbhd?.svg_bar_nbhd
            ?.selectAll('rect')
            .style('opacity', (d) =>
              selected_nbhds.includes(d.name) ? 1.0 : 0.2
            );
        }
      } else if (
        entitiesMatch(rowEntity, colEntity) &&
        is_neighborhood(rowEntity)
      ) {
        // Same entity:attr on both axes for neighborhoods (nbhd-nbhd matrix)
        // Highlight BOTH neighborhoods in the Landscape
        const selected_nbhds = [row.name, col.name];
        viz_state.obs_store.selected_nbhds.set(selected_nbhds);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'cell_layer');

        if (viz_state.nbhd?.svg_bar_nbhd) {
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) =>
              selected_nbhds.includes(d.name) ? 1.0 : 0.2
            );
        }
      }
    }
  } catch (error) {
    handleAsyncError(error, {
      context: 'updating IST landscape from CGM',
      logUnexpected: true,
      throwOnAuth: false,
    });
  }
};
