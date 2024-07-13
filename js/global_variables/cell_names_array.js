export let cell_names_array = []

export const set_cell_names_array = (cell_arrow_table) => {
    cell_names_array = cell_arrow_table.getChild("name").toArray();
}

export let cell_name_to_index_map = new Map()

export const set_cell_name_to_index_map = () => {
    // move this to a set function later
    cell_names_array.forEach((name, index) => {
        cell_name_to_index_map.set(name, index)
    })
}