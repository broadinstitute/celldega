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

export const sync_selected_genes = (viz_state, genes) => {
  if (viz_state.model && typeof viz_state.model.set === 'function') {
    viz_state.model.set('selected_genes', genes);
    viz_state.model.save_changes();
  }

  if (viz_state.obs_store && viz_state.obs_store.selected_genes) {
    viz_state.obs_store.selected_genes.set(genes);
  }
};
