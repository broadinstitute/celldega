export let selected_cats = []

export const update_selected_cats = (new_selected_cats) => {
    // Check if the arrays are equal
    const areArraysEqual = new_selected_cats.length === selected_cats.length &&
                           new_selected_cats.every((value, index) => value === selected_cats[index])

    // Use the ternary operator to update selected_cats
    selected_cats = areArraysEqual ? [] : new_selected_cats
}