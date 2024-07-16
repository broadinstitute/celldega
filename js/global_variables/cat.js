import { cell_names_array } from "./cell_names_array"

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
    // cell_cats_dict = cell_names.reduce((acc, name, index) => (acc[name] = categories[index], acc), {})

    cell_names_array.forEach((name, index) => {
        dict_cell_cats[name] = cell_cats[index]
    })

}