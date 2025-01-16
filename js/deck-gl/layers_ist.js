export const get_layers_list = (layers_obj, viz_state, nbhd=false) => {

    const close_up = viz_state.close_up

    let layers_list

    if (viz_state.img.state){
        if (close_up) {
            layers_list = [
                layers_obj.background_layer,
                ...layers_obj.image_layers,
                layers_obj.edit_layer,
                layers_obj.path_layer,
                layers_obj.cell_layer,
                layers_obj.trx_layer,
                layers_obj.nbhd_layer,
            ]
        } else {
            layers_list = [
                layers_obj.background_layer,
                ...layers_obj.image_layers,
                layers_obj.cell_layer,
                layers_obj.edit_layer,
                layers_obj.nbhd_layer,
            ]
        }
    } else {

        if (close_up) {
            layers_list = [
                // layers_obj.background_layer,
                // ...layers_obj.image_layers,
                layers_obj.edit_layer,
                // layers_obj.path_layer,
                layers_obj.cell_layer,
                // layers_obj.trx_layer,
                layers_obj.nbhd_layer,
            ]
        } else {
            layers_list = [
                // layers_obj.background_layer,
                // ...layers_obj.image_layers,
                layers_obj.cell_layer,
                layers_obj.edit_layer,
                layers_obj.nbhd_layer,
            ]
        }
    }

    return layers_list

}