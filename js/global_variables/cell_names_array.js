export let cell_names_array = []

export const set_cell_names_array = (cell_arrow_table) => {
    cell_names_array = cell_arrow_table.getChild("name").toArray();
}