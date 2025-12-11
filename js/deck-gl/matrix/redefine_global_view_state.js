// Static view states that never change (for attribute labels)
const get_static_view_states = (viz_state) => ({
  row_attr_labels: {
    // Match the rows view x-target so bars and labels align horizontally
    target: [viz_state.viz.label_row_x, viz_state.viz.col_region / 2],
    zoom: [0, 0],
  },
  col_attr_labels: {
    // Use centered view for simple 1:1 coordinate mapping
    target: [
      (viz_state.viz.dendrogram_width + 60) / 2,
      viz_state.viz.col_region / 2,
    ],
    zoom: [0, 0],
  },
});

export const redefine_global_view_state = (
  viz_state,
  viewId,
  zoom_curated,
  pan_curated
) => {
  let globalViewState;

  // Get static view states that should never change
  const staticStates = get_static_view_states(viz_state);

  if (viewId === 'matrix') {
    globalViewState = {
      matrix: {
        zoom: [zoom_curated[0], zoom_curated[1]],
        target: [pan_curated[0], pan_curated[1]],
      },
      rows: {
        zoom: [viz_state.zoom.ini_zoom_x, zoom_curated[1]],
        target: [viz_state.viz.label_row_x, pan_curated[1]],
      },
      cols: {
        zoom: [zoom_curated[0], viz_state.zoom.ini_zoom_y],
        target: [pan_curated[0], viz_state.viz.label_col_y],
      },
      dendro_rows: {
        zoom: [viz_state.zoom.ini_zoom_x, zoom_curated[1]],
        target: [viz_state.viz.label_row_x, pan_curated[1]],
      },
      dendro_cols: {
        zoom: [zoom_curated[0], viz_state.zoom.ini_zoom_y],
        target: [pan_curated[0], viz_state.viz.label_col_y],
      },
      ...staticStates,
    };
  } else if (viewId === 'cols' || viewId === 'dendro_cols') {
    globalViewState = {
      matrix: {
        zoom: [zoom_curated[0], zoom_curated[1]],
        target: [pan_curated[0], viz_state.zoom.min_pan_y],
      },
      rows: {
        zoom: [viz_state.zoom.ini_zoom_x, zoom_curated[1]],
        target: [viz_state.viz.label_row_x, viz_state.zoom.min_pan_y],
      },
      cols: {
        zoom: [zoom_curated[0], viz_state.zoom.ini_zoom_y],
        target: [pan_curated[0], viz_state.viz.label_col_y],
      },
      dendro_rows: {
        zoom: [viz_state.zoom.ini_zoom_x, zoom_curated[1]],
        target: [viz_state.viz.label_row_x, viz_state.zoom.min_pan_y],
      },
      dendro_cols: {
        zoom: [zoom_curated[0], viz_state.zoom.ini_zoom_y],
        target: [pan_curated[0], viz_state.viz.label_col_y],
      },
      ...staticStates,
    };
  } else if (viewId === 'rows' || viewId === 'dendro_rows') {
    globalViewState = {
      matrix: {
        zoom: [zoom_curated[0], zoom_curated[1]],
        target: [viz_state.zoom.min_pan_x, pan_curated[1]],
      },
      rows: {
        zoom: [viz_state.zoom.ini_zoom_x, zoom_curated[1]],
        target: [viz_state.viz.label_row_x, pan_curated[1]],
      },
      cols: {
        zoom: [zoom_curated[0], viz_state.zoom.ini_zoom_y],
        target: [pan_curated[0], viz_state.viz.label_col_y],
      },
      dendro_rows: {
        zoom: [viz_state.zoom.ini_zoom_x, zoom_curated[1]],
        target: [viz_state.viz.label_row_x, pan_curated[1]],
      },
      dendro_cols: {
        zoom: [zoom_curated[0], viz_state.zoom.ini_zoom_y],
        target: [pan_curated[0], viz_state.viz.label_col_y],
      },
      ...staticStates,
    };
  }

  return globalViewState;
};
