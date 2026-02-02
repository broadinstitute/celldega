export const update_selected_genes = (genes, new_selected_genes, obs_store) => {
  // Check if the arrays are equal
  const areArraysEqual =
    new_selected_genes.length === genes.selected_genes.length &&
    new_selected_genes.every(
      (value, index) => value === genes.selected_genes[index]
    );

  // Use the ternary operator to update selected_genes
  genes.selected_genes = areArraysEqual ? [] : new_selected_genes;

  // Update obs_store
  obs_store.selected_genes.set(genes.selected_genes);
};

/**
 * Check if a row entity represents gene data (for enrichment purposes).
 * This checks both entity === 'gene' and data_type === 'gene'.
 * The data_type field allows entities like 'nbhd_gene' to enable enrichment
 * even though their spatial context is neighborhoods.
 */
const isGeneEntity = (row_entity) => {
  if (!row_entity) return false;
  // Check entity name directly
  if (row_entity.entity === 'gene') return true;
  // Check entity names that imply gene data
  if (row_entity.entity === 'nbhd_gene') return true;
  // Check explicit data_type field (most flexible)
  if (row_entity.data_type === 'gene') return true;
  return false;
};

export const sync_selected_genes = (viz_state, genes) => {
  // Get current value before setting to verify sync is working
  const currentValue = viz_state.model?.get?.('selected_genes');
  
  console.log('sync_selected_genes called:', {
    genes_count: genes?.length,
    genes_sample: genes?.slice(0, 3),
    has_model: !!viz_state.model,
    has_set: typeof viz_state.model?.set === 'function',
    has_save_changes: typeof viz_state.model?.save_changes === 'function',
    current_selected_genes: currentValue?.length ?? 'N/A',
    row_entity: viz_state.row_entity,
  });

  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_genes', genes);

    // Also sync to selected_rows if row entity represents genes
    const { row_entity } = viz_state;
    if (isGeneEntity(row_entity)) {
      viz_state.model.set('selected_rows', genes);
    }

    if (typeof viz_state.model.save_changes === 'function') {
      viz_state.model.save_changes();
      console.log('sync_selected_genes: saved changes, new value:', viz_state.model.get('selected_genes')?.length);
    } else {
      console.warn('sync_selected_genes: model.save_changes is not a function');
    }
  } else {
    console.warn('sync_selected_genes: model not available or missing set function');
  }

  if (viz_state.obs_store && viz_state.obs_store.selected_genes) {
    viz_state.obs_store.selected_genes.set(genes);
  }
};

/**
 * Sync selected rows to the Python model.
 * Also syncs to selected_genes if row entity represents genes
 * (entity === 'gene' OR data_type === 'gene').
 */
export const sync_selected_rows = (viz_state, rows) => {
  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_rows', rows);

    // Also sync to selected_genes if row entity represents genes
    const { row_entity } = viz_state;
    if (isGeneEntity(row_entity)) {
      viz_state.model.set('selected_genes', rows);
    }

    viz_state.model.save_changes();
  }
};

/**
 * Sync selected columns to the Python model.
 */
export const sync_selected_cols = (viz_state, cols) => {
  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_cols', cols);
    viz_state.model.save_changes();
  }
};
