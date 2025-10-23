export const update_selected_proteins = (
  proteins,
  new_selected_proteins,
  obs_store
) => {
  const areArraysEqual =
    new_selected_proteins.length === proteins.selected_proteins.length &&
    new_selected_proteins.every(
      (value, index) => value === proteins.selected_proteins[index]
    );

  proteins.selected_proteins = areArraysEqual
    ? []
    : new_selected_proteins;

  if (obs_store && obs_store.selected_proteins) {
    obs_store.selected_proteins.set(proteins.selected_proteins);
  }
};
