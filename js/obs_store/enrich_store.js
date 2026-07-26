import { Observable } from './observable';

export const create_enrich_store = () => {
  const store = {
    available_libs: Observable([]),
    selected_lib: Observable('CellMarker_2024'),
    term_genes: Observable([]),
    gene_of_interest: Observable(''),
    selected_term: Observable('Select Term'),
  };

  return store;
};
