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

const enrichmentSelection = (viz_state, selectedGenes) => {
  const { model } = viz_state;
  if (!model?.get || model.get('component') !== 'Matrix') return null;

  const clickType = String(viz_state.click?.type || '').toLowerCase();
  const clickValue = viz_state.click?.value || {};

  // A row label is a focus/navigation action, not a gene-set selection.
  // Leaving enrichment_genes untouched preserves the current Enrich results.
  if (!clickType || clickType === 'row_label') return null;

  let enabled = false;
  let sourceLabel = 'Selection';

  if (clickType === 'col_label') {
    enabled = true;
    sourceLabel = String(clickValue.name || 'Column selection');
  } else if (clickType.startsWith('row')) {
    enabled = Boolean(model.get('row_enrich_enabled'));
    sourceLabel =
      clickValue.crop_source === 'dendrogram' || clickType === 'row_dendro'
        ? 'Dendrogram selection'
        : 'Brush selection';
  } else if (clickType.startsWith('col')) {
    enabled = Boolean(model.get('col_enrich_enabled'));
    sourceLabel =
      clickValue.crop_source === 'dendrogram' || clickType === 'col_dendro'
        ? 'Dendrogram selection'
        : 'Brush selection';
  }

  if (!enabled) return null;
  return {
    genes: selectedGenes,
    sourceLabel: selectedGenes.length ? sourceLabel : '',
  };
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

    const enrichment = enrichmentSelection(viz_state, selectedGenes);
    if (enrichment) {
      viz_state.model.set('enrichment_genes', enrichment.genes);
      viz_state.model.set('enrichment_source_label', enrichment.sourceLabel);
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
