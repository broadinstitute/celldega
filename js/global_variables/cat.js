import { cell_names_array } from "./cell_names_array"

// // cat can be 'cluster' or a gene name
// // if cat is a gene name then the cells will be colored based on gene expression
// // if cat is 'cluster' then the cells will be colored based on the cell category
// // and 'cluster' can be filtered using selected_cats. This can be used to filter
// // for a subset of cell cluster categories.

export const update_cat = (cats, new_cat) => {
    cats.cat = new_cat
}

export const set_cell_cats = (cats, cell_arrow_table, column_name) => {
    cats.cell_cats = cell_arrow_table.getChild(column_name).toArray()
}

export const update_cell_cats = (cats, new_cell_cats) => {
    // swap 'nan' for null in new cats
    cats.cell_cats = new_cell_cats.map(cat => cat === 'nan' ? null : cat)
}

export const set_dict_cell_cats = (cats) => {

    cell_names_array.forEach((name, index) => {
        cats.dict_cell_cats[name] = cats.cell_cats[index]
    })

}

export const update_selected_cats = (cats, new_selected_cats) => {
    // Check if the arrays are equal
    cats.reset_cat = new_selected_cats.length === cats.selected_cats.length &&
                           new_selected_cats.every((value, index) => value === cats.selected_cats[index])

    // Use the ternary operator to update selected_cats
    cats.selected_cats = cats.reset_cat ? [] : new_selected_cats
}