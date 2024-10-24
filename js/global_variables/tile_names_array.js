
export const set_tile_names_array = (cats, new_tile_names_array) => {
    cats.tile_names_array = new_tile_names_array
}

export const set_tile_name_to_index_map = (cats) => {

    cats.tile_name_to_index_map = new Map()

    // move this to a set function later
    cats.tile_names_array.forEach((name, index) => {
        cats.tile_name_to_index_map.set(name, index)
    })
}