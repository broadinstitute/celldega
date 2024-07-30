import { cell_names_array } from "./cell_names_array"

// cat can be 'cluster' or a gene name
// if cat is a gene name then the cells will be colored based on gene expression
// if cat is 'cluster' then the cells will be colored based on the cell category
// and 'cluster' can be filtered using selected_cats. This can be used to filter
// for a subset of cell cluster categories.
export let cat

export let reset_cat = false

export const update_cat = (new_cat) => {
    cat = new_cat
}

export let cell_cats

export const set_cell_cats = (cell_arrow_table, column_name) => {
    cell_cats = cell_arrow_table.getChild(column_name).toArray()
}

export const update_cell_cats = (new_cell_cats) => {

    // swap 'nan' for null in new_cell_cats
    new_cell_cats = new_cell_cats.map(cat => cat === 'nan' ? null : cat)
    cell_cats = new_cell_cats

    set_dict_cell_cats()
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
    reset_cat = new_selected_cats.length === selected_cats.length &&
                           new_selected_cats.every((value, index) => value === selected_cats[index])

    // Use the ternary operator to update selected_cats
    selected_cats = reset_cat ? [] : new_selected_cats
}