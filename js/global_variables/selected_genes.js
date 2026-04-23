export const update_selected_genes = (genes, new_selected_genes, obs_store) => {
  // Check if the arrays are equal
  const areArraysEqual =
    new_selected_genes.length === genes.selected_genes.length &&
    new_selected_genes.every(
      (value, index) => value === genes.selected_genes[index]
    );

  // Use the ternary operator to update selected_genes
  genes.selected_genes = areArraysEqual ? [] : new_selected_genes;
  genes.selected_gene_ids = new Set(
    genes.selected_genes
      .map((gene) => genes.g_nameMapping?.[gene])
      .filter((geneId) => geneId !== undefined)
  );

  // Update obs_store
  obs_store.selected_genes.set(genes.selected_genes);
};

export const sync_selected_genes = (viz_state, genes) => {
  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_genes', genes);

    // Also sync to selected_rows if row entity is 'gene'
    const { row_entity } = viz_state;
    if (row_entity?.entity === 'gene') {
      viz_state.model.set('selected_rows', genes);
    }

    viz_state.model.save_changes();
  }

  if (viz_state.obs_store && viz_state.obs_store.selected_genes) {
    viz_state.genes.selected_gene_ids = new Set(
      genes
        .map((gene) => viz_state.genes.g_nameMapping?.[gene])
        .filter((geneId) => geneId !== undefined)
    );
    viz_state.obs_store.selected_genes.set(genes);
  }
};

/**
 * Sync selected rows to the Python model.
 * Also syncs to selected_genes if row entity is 'gene'.
 */
export const sync_selected_rows = (viz_state, rows) => {
  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_rows', rows);

    // Also sync to selected_genes if row entity is 'gene'
    const { row_entity } = viz_state;
    if (row_entity?.entity === 'gene') {
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
