export const set_cell_names_array = (cats, cell_arrow_table) => {

    // Extract the array of names (strings)
    cats.cell_names_array = cell_arrow_table.getChild("name").toArray();

    // Create a set of unique names
    const uniqueNames = [...new Set(cats.cell_names_array)];

    // Create a mapping from name to a unique integer index
    const nameMapping = uniqueNames.reduce((acc, name, idx) => {
    acc[name] = idx;
    return acc;
    }, {});

    // Create the reverse mapping: integer index to name
    const nameMapping_inv = uniqueNames.reduce((acc, name, idx) => {
        acc[idx] = name;
        return acc;
    }, {});

    // Save the mapping and inverse mapping as cats.nameMapping_inv
    cats.nameMapping = nameMapping;
    cats.nameMapping_inv = nameMapping_inv;

}

export const set_cell_name_to_index_map = (cats) => {
    cats.cell_names_array.forEach((name, index) => {
        cats.cell_name_to_index_map.set(name, index)
    })
}