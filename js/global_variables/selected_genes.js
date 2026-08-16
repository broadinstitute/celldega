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
 * Force the selected-gene state to exactly `new_selected_genes`, skipping
 * update_selected_genes' "same array toggles off" heuristic. Crucially this
 * keeps genes.selected_gene_ids (the Set the transcript layer reads to focus a
 * gene) in sync -- assigning genes.selected_genes directly leaves that Set
 * stale, so the trx layer never dims the other genes' transcripts.
 */
export const force_set_selected_genes = (
  genes,
  new_selected_genes,
  obs_store
) => {
  const selectedGenes = Array.isArray(new_selected_genes)
    ? new_selected_genes
    : [];
  updateSelectedGeneState(genes, selectedGenes);

  if (obs_store?.selected_genes) {
    obs_store.selected_genes.set(selectedGenes);
  }
};

export const sync_selected_genes = (viz_state, genes) => {
  const selectedGenes = Array.isArray(genes) ? genes : [];

  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_genes', selectedGenes);

    // Also sync to selected_rows if row entity is 'gene'
    const { row_entity } = viz_state;
    if (row_entity?.entity === 'gene') {
      viz_state.model.set('selected_rows', selectedGenes);
    }

    viz_state.model.save_changes();
  }

  updateSelectedGeneState(viz_state.genes, selectedGenes);

  if (viz_state.obs_store?.selected_genes) {
    viz_state.obs_store.selected_genes.set(selectedGenes);
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
