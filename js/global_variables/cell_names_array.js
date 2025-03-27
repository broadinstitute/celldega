export const set_cell_names_array = (cats, cell_arrow_table) => {

    // Extract the array of names (strings)
    cats.cell_names_array = cell_arrow_table.getChild("name").toArray();

    // Create the reverse mapping: integer index to name
    const nameMapping_inv = cats.cell_names_array.reduce((acc, name, idx) => {
        acc[idx] = name;
        return acc;
    }, {});

    // Save the mapping 
    cats.nameMapping_inv = nameMapping_inv;

}

export const set_cell_name_to_index_map = (cats) => {
    cats.cell_names_array.forEach((name, index) => {
        name = String(name)
        cats.cell_name_to_index_map.set(name, index)
    })
}