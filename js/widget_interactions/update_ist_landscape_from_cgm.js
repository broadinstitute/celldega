import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import {
  update_selected_genes,
  sync_selected_genes,
} from '../global_variables/selected_genes';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { refresh_layer } from '../utils/refresh_layer';

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
export const isCellCluster = (clickValue) => {
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
export const isNeighborhood = (clickValue) => {
  if (!clickValue) return false;

  // Legacy format check
  if (clickValue.col_entity === 'nbhd') return true;

  // New format check
  return clickValue.entity === 'nbhd' || clickValue.entity === 'hextile';
};

/**
 * Check if a click value represents a gene selection.
 */
export const isGene = (clickValue) => {
  if (!clickValue) return false;

  // New format check
  return clickValue.entity === 'gene';
};

/**
 * Check if a click value represents an individual cell selection.
 * This is when entity is 'cell' and attr is 'name' (not a cluster attribute).
 */
export const isCell = (clickValue) => {
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
      // Check if this is a cell cluster selection using entity/attr
      if (isCellCluster(click_info.value)) {
        inst_gene = 'cluster';
        new_cat = click_info.value.name;

        // Clear selected cells when switching to cluster mode
        viz_state.obs_store.selected_cells.set([]);

        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else {
        // Treat as gene selection
        inst_gene = click_info.value.name;

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
          viz_state.aws
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
    } else if (click_type === 'col_label') {
      // Check if this is a neighborhood selection
      if (isNeighborhood(click_info.value)) {
        const new_nbhd = click_info.value.name;
        viz_state.obs_store.selected_nbhds.set([new_nbhd]);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) => (d.name === new_nbhd ? 1.0 : 0.2));

          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .filter((d) => d.name === new_nbhd)
            .node()
            ?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            });
        } else {
          viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
        }
      } else if (isCell(click_info.value)) {
        // Individual cell selection - highlight in landscape
        const cell_name = strip_cell_prefix(click_info.value.name, viz_state);
        viz_state.obs_store.selected_cells.set([cell_name]);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else {
        inst_gene = 'cluster';
        new_cat = click_info.value.name;

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
    } else if (click_type === 'col_dendro') {
      const new_cats = click_info.value.selected_names || [];
      const is_unselecting = click_info.value.is_unselecting || new_cats.length === 0;

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
      if (isNeighborhood(col_entity_full)) {
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
      } else if (isCell(col_entity_full)) {
        // Individual cells selected via dendrogram - highlight in landscape
        const stripped_cells = strip_cell_prefixes(new_cats, viz_state);
        viz_state.obs_store.selected_cells.set(stripped_cells);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
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
      const is_unselecting = click_info.value.is_unselecting || new_cats.length === 0;

      // Handle unselection - clear all states and return to cluster mode
      if (is_unselecting) {
        reset_to_cluster_mode(viz_state, layers_obj);
        refresh_layer(viz_state, layers_obj, 'trx_layer');
        return;
      }

      // Check if rows represent cell clusters
      const row_entity_full =
        click_info.value.row_entity_full || click_info.value;
      if (isCellCluster(row_entity_full)) {
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
      } else if (isGene(row_entity_full)) {
        // Gene selection from row dendrogram
        update_selected_genes(viz_state.genes, new_cats, viz_state.obs_store);

        sync_selected_genes(viz_state, viz_state.genes.selected_genes);

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
      const { axis, attr_name, value, node_names } = click_info.value;
      const col_entity_full = click_info.value.col_entity_full;

      // If columns are cells and we clicked a category on the column axis
      if (axis === 'col' && isCell(col_entity_full)) {
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
      if (isCellCluster(rowEntity) && isNeighborhood(colEntity)) {
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
      } else if (entitiesMatch(rowEntity, colEntity) && isCellCluster(rowEntity)) {
        // Same entity:attr on both axes (e.g., cluster-cluster similarity matrix)
        // Highlight BOTH clusters in the Landscape
        viz_state.obs_store.selected_cells.set([]);
        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        update_cat(viz_state.cats, 'cluster');
        // Select both the row and column clusters
        const selected_clusters = [row.name, col.name];
        update_selected_cats(viz_state.cats, selected_clusters, viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else if (isGene(rowEntity) && isCellCluster(colEntity)) {
        // Gene (row) x Cluster (col): Show gene expression filtered to cluster
        const gene_name = row.name;
        const cluster_name = col.name;

        // Clear any previous cell selection
        viz_state.highlighted_cells = new Set();
        viz_state.obs_store.selected_cells.set([]);

        // Set the gene as the category for coloring
        update_cat(viz_state.cats, gene_name);
        update_selected_genes(viz_state.genes, [gene_name], viz_state.obs_store);

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
        update_selected_cats(viz_state.cats, [cluster_name], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      } else if (isCellCluster(rowEntity) && isGene(colEntity)) {
        // Cluster (row) x Gene (col): Show gene expression filtered to cluster
        const cluster_name = row.name;
        const gene_name = col.name;

        // Clear any previous cell selection
        viz_state.highlighted_cells = new Set();
        viz_state.obs_store.selected_cells.set([]);

        // Set the gene as the category for coloring
        update_cat(viz_state.cats, gene_name);
        update_selected_genes(viz_state.genes, [gene_name], viz_state.obs_store);

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
        update_selected_cats(viz_state.cats, [cluster_name], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
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
