export let cat

export const update_cat = (new_cat) => {
    cat = new_cat
}

export let cell_cats

export const set_cell_cats = (cell_arrow_table, column_name) => {
    cell_cats = cell_arrow_table.getChild(column_name).toArray();
}
