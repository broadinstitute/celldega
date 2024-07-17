import { cell_names_array } from "./cell_names_array"

// cat can be 'cluster' or 'gene'
export let cat

export const update_cat = (new_cat) => {
    cat = new_cat
}

export let cell_cats

export const set_cell_cats = (cell_arrow_table, column_name) => {
    cell_cats = cell_arrow_table.getChild(column_name).toArray();
}

export let dict_cell_cats = {}

export const set_dict_cell_cats = () => {

    cell_names_array.forEach((name, index) => {
        dict_cell_cats[name] = cell_cats[index]
    })

}

export let selected_cats = []

export const update_selected_cats = (new_selected_cats) => {
    // Check if the arrays are equal
    const areArraysEqual = new_selected_cats.length === selected_cats.length &&
                           new_selected_cats.every((value, index) => value === selected_cats[index])

    // Use the ternary operator to update selected_cats
    selected_cats = areArraysEqual ? [] : new_selected_cats
}