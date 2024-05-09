export let selected_cats = []

export const update_selected_cats = (new_selected_cats) => {

    // if new_selected_cats is equal to selected_cats then set selected_cats to an empty array
    if (new_selected_cats.length === selected_cats.length && new_selected_cats.every((value, index) => value === selected_cats[index])) {
        selected_cats = []
        return
    } else {
        selected_cats = new_selected_cats
    }
}