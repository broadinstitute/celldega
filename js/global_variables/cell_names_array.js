import {
  getRowKeyArray,
  getTableColumnArray,
} from '../read_parquet/table_accessors';

export const set_cell_names_array = (cats, cell_arrow_table) => {
  cats.cell_ids_are_indexed = false;
  // Extract the array of names (strings)
  const nameColumn = getTableColumnArray(cell_arrow_table, [
    'name',
    'cell_id',
    '__index_level_0__',
  ]);
  cats.cell_names_array =
    nameColumn.length > 0
      ? nameColumn.map((name) => String(name))
      : getRowKeyArray(cell_arrow_table);

  // cell_names_array already provides the integer index -> name mapping.
  cats.nameMapping_inv = cats.cell_names_array;
};

// Compact CellCloud files repeat uint32 row positions instead of cell names.
// The separate identity table stores the original IDs once for linking and
// tooltips; geometry and expression remain in that canonical row order.
export const set_indexed_cell_names_array = (
  cats,
  geometry_table,
  identity_table
) => {
  const indices = getTableColumnArray(geometry_table, 'name');
  const names = getTableColumnArray(identity_table, 'name');
  if (
    names.length !== geometry_table.numRows ||
    indices.length !== names.length ||
    !indices.every((index, row) => Number(index) === row)
  ) {
    throw new Error(
      '[CellCloud] Indexed geometry must follow the cell_ids row order (0..n-1).'
    );
  }
  cats.cell_names_array = names.map(String);
  cats.nameMapping_inv = cats.cell_names_array;
  cats.cell_ids_are_indexed = true;
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
