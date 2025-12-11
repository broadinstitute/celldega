export const get_mat_layers_list = (layers_mat) => {
  const layers_list = [
    layers_mat.mat_layer,
    layers_mat.row_cat_layer,
    layers_mat.col_cat_layer,
    layers_mat.row_label_layer,
    layers_mat.col_label_layer,
    layers_mat.row_dendro_layer,
    layers_mat.col_dendro_layer,
  ];

  // Add attribute label layers if they exist
  if (layers_mat.col_attr_label_layer) {
    layers_list.push(layers_mat.col_attr_label_layer);
  }
  if (layers_mat.row_attr_label_layer) {
    layers_list.push(layers_mat.row_attr_label_layer);
  }

  return layers_list;
};

export const layer_filter = ({ layer, viewport }) => {
  if (viewport.id === 'matrix' && layer.id.includes('mat-layer')) {
    return true;
  } else if (viewport.id === 'rows' && layer.id === 'row-layer') {
    return true;
  } else if (viewport.id === 'cols' && layer.id === 'col-layer') {
    return true;
  } else if (viewport.id === 'rows' && layer.id.includes('row-label-layer')) {
    return true;
  } else if (viewport.id === 'cols' && layer.id === 'col-label-layer') {
    return true;
  } else if (
    (viewport.id === 'dendro_rows') &
    (layer.id === 'row-dendro-layer')
  ) {
    return true;
  } else if (viewport.id === 'dendro_cols' && layer.id === 'col-dendro-layer') {
    return true;
  } else if (viewport.id === 'col_attr_labels' && layer.id === 'col-attr-label-layer') {
    // Column attribute labels appear in a static view at the right
    return true;
  } else if (viewport.id === 'row_attr_labels' && layer.id === 'row-attr-label-layer') {
    // Row attribute labels appear in a static view at the top-left
    return true;
  }

  return false;
};
