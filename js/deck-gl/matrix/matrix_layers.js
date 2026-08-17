import {
  crop_fade_signature,
  crop_filter_signature,
} from '../../matrix/crop_filter';

export const get_matrix_body_layer_id = (viz_state) => {
  const rev = viz_state.mat?._body_layer_rev || 0;
  return rev > 0 ? `mat-layer-${rev}` : 'mat-layer';
};

/**
 * Shared updateTriggers for the matrix body layer at reorder time. Keying
 * getPosition/getSize/getRadius off the current order (plus mode + composition
 * normalization) ensures both the heatmap (position) and composition
 * (position + per-segment size) bodies refresh on any reorder.
 *
 * @param {object} viz_state - Visualization state.
 * @param {Array} [extra] - Extra values to fold into the trigger key.
 * @returns {object} updateTriggers object for a mat-layer clone.
 */
export const mat_reorder_triggers = (viz_state, extra = []) => {
  const key = [
    viz_state.order.current.row,
    viz_state.order.current.col,
    viz_state.mat.viz_mode,
    viz_state.mat.composition_normalized,
    crop_filter_signature(viz_state),
    crop_fade_signature(viz_state),
    ...extra,
  ];
  return {
    getPosition: key,
    getSize: key,
    getRadius: key,
    getFillColor: [
      ...key,
      viz_state.mat?.comp_hover_row,
      viz_state.mat?.comp_hover_col,
      viz_state.dendro?._highlight_rev || 0,
    ],
  };
};

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
  } else if (viewport.id === 'dendro_rows' && layer.id === 'row-dendro-layer') {
    return true;
  } else if (viewport.id === 'dendro_cols' && layer.id === 'col-dendro-layer') {
    return true;
  } else if (
    viewport.id === 'col_attr_labels' &&
    layer.id === 'col-attr-label-layer'
  ) {
    // Column attribute labels appear in a static view at the right
    return true;
  } else if (
    viewport.id === 'row_attr_labels' &&
    layer.id === 'row-attr-label-layer'
  ) {
    // Row attribute labels appear in a static view at the top-left
    return true;
  }

  return false;
};
