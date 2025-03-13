export const set_cell_names_array = (cats, cell_arrow_table) => {
    cats.cell_names_array = cell_arrow_table.getChild("name").toArray();
}

export const set_cell_name_to_index_map = (cats) => {
    cats.cell_names_array.forEach((name, index) => {
        cats.cell_name_to_index_map.set(name, index)
    })
}