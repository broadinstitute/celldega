import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';
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
 * Helper to reset neighborhood layer to categorical cluster coloring.
 * Call this when selecting neighborhoods from dendrogram (not by attribute).
 */
const reset_nbhd_to_cluster_mode = (viz_state) => {
  if (!viz_state.nbhd) return;

  // Reset to categorical coloring
  viz_state.nbhd.color_mode = 'cluster';
  viz_state.nbhd.gene_expression = null;
  viz_state.nbhd.current_gene = null;

  // Show bar graph if it exists
  if (viz_state.containers?.bar_nbhd) {
    viz_state.containers.bar_nbhd.style.display = 'flex';
  }

  // Show opacity slider
  if (viz_state.sliders?.nbhd) {
    // Import toggle_slider dynamically is tricky, so just show the container
    const slider_container = viz_state.sliders.nbhd?.container;
    if (slider_container) {
      slider_container.style.display = 'flex';
    }
  }

  // Reset the dropdown to 'cluster' if it exists
  const dropdown = document.getElementById('nbhd-attr-dropdown');
  if (dropdown) {
    dropdown.value = 'cluster';
  }
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
 * Check if a click value represents a nbhd_var entity (or nbhd_gene).
 * Rows are attributes from nbhd_adata.var - clicking ALWAYS colors neighborhoods.
 * nbhd_gene is a special case where rows are genes aggregated at neighborhood level.
 */
export const is_nbhd_var = (clickValue) => {
  if (!clickValue) return false;
  return (
    clickValue.entity === 'nbhd_var' ||
    clickValue.entity === 'nbhd_attr' ||
    clickValue.entity === 'nbhd_gene'
  );
};

/**
 * Check if a click value represents gene data (for enrichment purposes).
 * This is true for entity='gene' OR entity='nbhd_gene' OR data_type='gene'.
 */
export const is_gene_data = (clickValue) => {
  if (!clickValue) return false;
  // Direct gene entity
  if (clickValue.entity === 'gene') return true;
  // nbhd_gene - genes at neighborhood level
  if (clickValue.entity === 'nbhd_gene') return true;
  // Explicit data_type (most flexible)
  if (clickValue.data_type === 'gene') return true;
  return false;
};

/**
 * Check if a click value represents a gene entity.
 * For strict entity check only - use is_gene_data() for enrichment purposes.
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
      // Check if this is a nbhd_var/nbhd_gene entity (attribute from nbhd_adata.var)
      // This ALWAYS colors neighborhoods - no fallback to cells
      if (is_nbhd_var(click_info.value)) {
        const attr_name = click_info.value.name;
        const has_nbhd_adata = viz_state.nbhd?.has_nbhd_adata;

        if (has_nbhd_adata) {
          // Send request to Python backend to get nbhd attribute data
          if (viz_state.model && typeof viz_state.model.set === 'function') {
            viz_state.model.set('nbhd_attr_request', attr_name);
            viz_state.model.save_changes();
          }

          // Show neighborhood layer, hide cell layer coloring
          viz_state.obs_store.viz_nbhd_layer.set(true);
          viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

          // Clear cell selections
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);

          // Update gene display name (for UI purposes only)
          if (viz_state.genes) {
            viz_state.genes.inst_gene = attr_name;
          }

          // If this is gene data (nbhd_gene or data_type='gene'), update local state
          // Note: Don't sync to Python here - the Clustergram handles that
          if (is_gene_data(click_info.value) && viz_state.genes) {
            viz_state.genes.selected_genes = [attr_name];
            viz_state.obs_store.selected_genes.set([attr_name]);
          }

          // DON'T refresh layer here - the traitlet handler will do it
          // after data arrives from Python via change:nbhd_attr_data
        }
      // Check if this is a neighborhood selection
      } else if (is_neighborhood(click_info.value)) {
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
        console.log('Entered is_cell_cluster block');
        // Cell cluster/population entity - can color nbhds OR highlight cells
        const attr_name = click_info.value.name;
        console.log('attr_name:', attr_name);
        const nbhd_is_active = viz_state.obs_store?.viz_nbhd_layer?.get() || false;
        console.log('nbhd_is_active:', nbhd_is_active);
        const has_nbhd_adata = viz_state.nbhd?.has_nbhd_adata || false;
        console.log('has_nbhd_adata:', has_nbhd_adata);

        console.log('row_label click - is_cell_cluster:', {
          attr_name,
          nbhd_is_active,
          has_nbhd_adata,
          entity: click_info.value.entity,
          attr: click_info.value.attr,
        });

        if (nbhd_is_active && has_nbhd_adata) {
          // NBHD active: Color neighborhoods by this attribute
          console.log('Sending nbhd_attr_request:', attr_name);
          update_selected_genes(viz_state.genes, [attr_name], viz_state.obs_store);

          if (viz_state.model && typeof viz_state.model.set === 'function') {
            viz_state.model.set('nbhd_attr_request', attr_name);
            viz_state.model.save_changes();
          }

        update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);
          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        } else {
          // CELL active: Highlight cells with this population/cluster
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [attr_name], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'trx_layer');
        }
      } else {
        // Treat as gene selection (or nbhd attribute if NBHD is active)
        inst_gene = click_info.value.name;

        // Check if NBHD layer is active - if so, color nbhds instead of cells
        const nbhd_is_active = viz_state.obs_store.viz_nbhd_layer.get();
        const nbhd_has_adata = viz_state.nbhd?.has_nbhd_adata;

        console.log('row_label click - else block (gene/other):', {
          inst_gene,
          nbhd_is_active,
          nbhd_has_adata,
          entity: click_info.value.entity,
          attr: click_info.value.attr,
        });

        if (nbhd_is_active && nbhd_has_adata) {
          // MUTUALLY EXCLUSIVE: Color neighborhoods by this attribute
          console.log('Sending nbhd_attr_request from else block:', inst_gene);
          update_selected_genes(
            viz_state.genes,
            [inst_gene],
            viz_state.obs_store
          );

          // Request neighborhood attribute data from Python
          if (viz_state.model && typeof viz_state.model.set === 'function') {
            viz_state.model.set('nbhd_attr_request', inst_gene);
            viz_state.model.save_changes();
          }

          // Keep cells in cluster mode (don't color by gene)
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);

          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        } else {
          // MUTUALLY EXCLUSIVE: Color cells by gene expression
        new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

          // Clear highlighted cells immediately
        viz_state.highlighted_cells = new Set();

        update_cat(viz_state.cats, new_cat);
        update_selected_genes(
          viz_state.genes,
          [inst_gene],
          viz_state.obs_store
        );

          // Load gene expression data for cells
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

        viz_state.obs_store.selected_cells.set([]);

        update_selected_cats(
          viz_state.cats,
          new_cat === 'cluster' ? [] : [inst_gene],
          viz_state.obs_store
        );

          // Hide nbhd layer when coloring cells
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
        // Reset to categorical cluster coloring (not attribute coloring)
        reset_nbhd_to_cluster_mode(viz_state);

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
      } else if (is_nbhd_var(row_entity_full)) {
        // nbhd_var/nbhd_gene selection from row dendrogram - ALWAYS color neighborhoods
        const has_nbhd_adata = viz_state.nbhd?.has_nbhd_adata;

        if (has_nbhd_adata) {
          // Send attr names to Python (comma-separated for averaging if multiple)
          if (viz_state.model && typeof viz_state.model.set === 'function') {
            viz_state.model.set('nbhd_attr_request', new_cats.join(','));
            viz_state.model.save_changes();
          }

          // Show neighborhood layer
          viz_state.obs_store.viz_nbhd_layer.set(true);
          viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

          // Update gene display name (for UI purposes)
          if (viz_state.genes) {
            viz_state.genes.inst_gene = new_cats.length === 1
              ? new_cats[0]
              : `avg(${new_cats.length} attrs)`;
          }

          // Clear cell selections
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);

          // If this is gene data (nbhd_gene or data_type='gene'), update local state
          // Note: Don't sync to Python here - the Clustergram handles that
          if (is_gene_data(row_entity_full) && viz_state.genes) {
            viz_state.genes.selected_genes = new_cats;
            viz_state.obs_store.selected_genes.set(new_cats);
          }
        }
      } else if (is_cell_cluster(row_entity_full)) {
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

        // Check if NBHD layer is active - mutually exclusive behavior
        const nbhd_is_active = viz_state.obs_store.viz_nbhd_layer.get();
        const nbhd_has_adata = viz_state.nbhd?.has_nbhd_adata;

        if (nbhd_is_active && nbhd_has_adata) {
          // MUTUALLY EXCLUSIVE: Color neighborhoods by gene(s)
          if (viz_state.model && typeof viz_state.model.set === 'function') {
            viz_state.model.set('nbhd_attr_request', new_cats.join(','));
            viz_state.model.save_changes();
          }

          // Keep cells in cluster mode
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);

          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        } else {
          // MUTUALLY EXCLUSIVE: Color cells by gene expression
        if (new_cats.length === 1) {
          inst_gene = new_cats[0];
          new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

          viz_state.highlighted_cells = new Set();
          update_cat(viz_state.cats, new_cat);

          await update_cell_exp_array(
            viz_state.cats,
            viz_state.genes,
            viz_state.global_base_url,
            inst_gene,
            viz_state.seg.version,
            viz_state.vector_name_integer,
            viz_state.aws
          );

          viz_state.obs_store.selected_cells.set([]);
          update_selected_cats(
            viz_state.cats,
            new_cat === 'cluster' ? [] : [inst_gene],
            viz_state.obs_store
          );
        } else {
            // Multiple genes - switch to cluster mode for cells
          viz_state.highlighted_cells = new Set();
          viz_state.obs_store.selected_cells.set([]);
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);
        }

          // Hide nbhd layer when coloring cells
        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
        }
      } else {
        // Other entity types (population, etc.) - treat as neighborhood attribute
        // This handles nbhd x population matrices where clicking population colors nbhds
        const nbhd_has_adata = viz_state.nbhd?.has_nbhd_adata;

        if (nbhd_has_adata && new_cats.length > 0) {
          // Request neighborhood attribute data for selected items
          if (viz_state.model && typeof viz_state.model.set === 'function') {
            viz_state.model.set('nbhd_attr_request', new_cats.join(','));
            viz_state.model.save_changes();
          }

          // Show neighborhood layer and set to attribute mode
          viz_state.nbhd.color_mode = 'gene';
          viz_state.obs_store.viz_nbhd_layer.set(true);
          viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

          refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        }
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
