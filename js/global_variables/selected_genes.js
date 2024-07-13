export let selected_genes = []

export const update_selected_genes = (new_selected_genes) => {
    // Check if the arrays are equal
    const areArraysEqual = new_selected_genes.length === selected_genes.length &&
                           new_selected_genes.every((value, index) => value === selected_genes[index]);

    // Use the ternary operator to update selected_genes
    selected_genes = areArraysEqual ? [] : new_selected_genes;
};
