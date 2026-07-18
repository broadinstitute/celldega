const updateSelectedGeneState = (genes, selectedGenes) => {
  if (!genes) {
    return;
  }

  genes.selected_genes = selectedGenes;
  genes.selected_gene_ids = new Set(
    selectedGenes
      .map((gene) => genes.g_nameMapping?.[gene])
      .filter((geneId) => geneId !== undefined)
  );
};

export const update_selected_genes = (genes, new_selected_genes, obs_store) => {
  const currentSelectedGenes = Array.isArray(genes?.selected_genes)
    ? genes.selected_genes
    : [];
  const nextSelectedGenes = Array.isArray(new_selected_genes)
    ? new_selected_genes
    : [];

  const areArraysEqual =
    nextSelectedGenes.length === currentSelectedGenes.length &&
    nextSelectedGenes.every(
      (value, index) => value === currentSelectedGenes[index]
    );

  const selectedGenes = areArraysEqual ? [] : nextSelectedGenes;
  updateSelectedGeneState(genes, selectedGenes);

  if (obs_store?.selected_genes) {
    obs_store.selected_genes.set(selectedGenes);
  }
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
  const selectedGenes = Array.isArray(genes) ? genes : [];

  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_genes', selectedGenes);

    // Also sync to selected_rows if row entity represents genes
    const { row_entity } = viz_state;
    if (isGeneEntity(row_entity)) {
      viz_state.model.set('selected_rows', selectedGenes);
    }

    if (typeof viz_state.model.save_changes === 'function') {
      viz_state.model.save_changes();
    }
  }

  updateSelectedGeneState(viz_state.genes, selectedGenes);

  if (viz_state.obs_store?.selected_genes) {
    viz_state.obs_store.selected_genes.set(selectedGenes);
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
