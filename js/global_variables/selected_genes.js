import { obs_store } from "../obs_store/obs_store";

export const update_selected_genes = (genes, new_selected_genes) => {

  console.log('update_selected_genes')

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
