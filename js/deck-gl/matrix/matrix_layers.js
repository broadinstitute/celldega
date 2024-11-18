export const get_mat_layers_list = (layers_mat) => {

    let layers_list = [
        layers_mat.mat_layer,
        layers_mat.row_cat_layer,
        layers_mat.col_cat_layer,
        layers_mat.row_label_layer,
        layers_mat.col_label_layer,
    ]

    return layers_list

}

export const layer_filter = ({layer, viewport}) => {

    if (viewport.id === 'matrix' && layer.id.includes('mat-layer')){
        return true
    } else if (viewport.id === 'rows' && layer.id === 'row-layer'){
        return true
    } else if (viewport.id === 'cols' && layer.id === 'col-layer'){
        return true
    } else if (viewport.id === 'rows' && layer.id.includes('row-label-layer')){
        return true
    } else if (viewport.id === 'cols' && layer.id === 'col-label-layer'){
        return true
    } else if (viewport.id === 'dendrogram_rows' & layer.id === 'row-dendro-layer') {
        return true
    }

    else if (viewport.id === 'dendrogram_cols' && layer.id === 'row-label-layer') {
        return true
    }

    return false

}