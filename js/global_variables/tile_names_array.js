export let tile_names_array

export const set_tile_names_array = (new_tile_names_array) => {
    tile_names_array = new_tile_names_array
}

export let tile_name_to_index_map = new Map()

export const set_tile_name_to_index_map = () => {
    // move this to a set function later
    tile_names_array.forEach((name, index) => {
        tile_name_to_index_map.set(name, index)
    })
}