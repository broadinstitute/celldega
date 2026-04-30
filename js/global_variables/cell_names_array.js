export const set_cell_names_array = (cats, cell_arrow_table) => {
  // Extract the array of names (strings)
  cats.cell_names_array = cell_arrow_table.getChild('name').toArray();

  // cell_names_array already provides the integer index -> name mapping.
  cats.nameMapping_inv = cats.cell_names_array;
};

export const set_cell_name_to_index_map = (cats) => {
  if (!(cats.cell_name_to_index_map instanceof Map)) {
    cats.cell_name_to_index_map = new Map();
  } else {
    cats.cell_name_to_index_map.clear();
  }

  cats.cell_names_array.forEach((name, index) => {
    name = String(name);
    cats.cell_name_to_index_map.set(name, index);
  });
};
