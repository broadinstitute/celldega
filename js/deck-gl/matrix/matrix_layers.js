export const get_layers_list = (layers_mat) => {

    let layers_list = [
        layers_mat.mat_layer,
        layers_mat.row_cat_layer,
        layers_mat.col_cat_layer,
        layers_mat.row_label_layer,
        layers_mat.col_label_layer,
    ]

    return layers_list

}