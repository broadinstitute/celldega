export const get_layers_list = (layers_obj, close_up) => {

    let layers_list

    if (close_up) {
        layers_list = [
            layers_obj.background_layer,
            ...layers_obj.image_layers,
            layers_obj.path_layer,
            layers_obj.cell_layer,
            layers_obj.edit_layer,
            layers_obj.trx_layer
        ]
    } else {
        layers_list = [
            layers_obj.background_layer,
            ...layers_obj.image_layers,
            layers_obj.cell_layer,
            layers_obj.edit_layer
        ]
    }

    return layers_list

}