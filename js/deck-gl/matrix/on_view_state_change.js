import { OrthographicView } from 'deck.gl';

import { refresh_row_label_visibility } from '../../matrix/composition_data';
import { get_zoomed_axis_label_font_size } from '../../matrix/crop_filter';

import { curate_pan_x, curate_pan_y } from './curate_pan';
import { clear_dendro_focus } from './dendro_layers';
import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { update_zoom_data } from './zoom';

export const on_view_state_change = (
  params,
  deck_mat,
  layers_mat,
  viz_state
) => {
  const { viewState } = params;
  const { viewId } = params;

  const { zoom, target } = viewState;

  const interaction = params.interactionState || {};
  const is_user_view_interaction =
    interaction.isZooming || interaction.isPanning || interaction.isDragging;

  if (is_user_view_interaction && !viz_state.dendro?._suppress_focus_clear) {
    clear_dendro_focus(deck_mat, layers_mat, viz_state, { render: false });
  }

  if (viz_state.dendro?._suppress_focus_clear && !is_user_view_interaction) {
    return;
  }

  // zoom differentials are calculated before the redefine_global_view_state function

  let zoom_dx;
  let zoom_dy;

  if (viewId === 'cols') {
    if (viz_state.zoom.minor_zoom_axis === 'X') {
      zoom_dx = zoom[0];
      zoom_dy = zoom[1];
    } else if (viz_state.zoom.minor_zoom_axis === 'Y') {
      zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
      zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;
    } else if (viz_state.zoom.minor_zoom_axis === 'none') {
      zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
      zoom_dy = zoom[1];
    }
  } else if (viewId === 'rows') {
    // console.log('checking zoom in rows', zoom)

    if (viz_state.zoom.minor_zoom_axis === 'Y') {
      zoom_dx = zoom[0];
      zoom_dy = zoom[1];
    } else if (viz_state.zoom.minor_zoom_axis === 'X') {
      zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
      zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;
    } else if (viz_state.zoom.minor_zoom_axis === 'none') {
      zoom_dx = zoom[0];
      zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;
    }
  } else if (viewId === 'dendro_rows') {
    // console.log('checking zoom in dendro_rows', zoom)

    if (viz_state.zoom.minor_zoom_axis === 'Y') {
      // console.log('minor zoom axis is Y')

      zoom_dx = zoom[0];
      zoom_dy = zoom[1];
    } else if (viz_state.zoom.minor_zoom_axis === 'X') {
      zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
      zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;
    } else if (viz_state.zoom.minor_zoom_axis === 'none') {
      zoom_dx = zoom[0];
      zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;

      // console.log(zoom)
      // console.log(zoom_dx, zoom_dy)
    }
  }
  if (viewId === 'dendro_cols') {
    if (viz_state.zoom.minor_zoom_axis === 'X') {
      zoom_dx = zoom[0];
      zoom_dy = zoom[1];
    } else if (viz_state.zoom.minor_zoom_axis === 'Y') {
      zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
      zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;
    } else if (viz_state.zoom.minor_zoom_axis === 'none') {
      zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
      zoom_dy = zoom[1];
    }
  } else if (viewId === 'matrix') {
    // console.log('checking zoom in matrix', zoom)

    zoom_dx = zoom[0] - viz_state.zoom.zoom_data[viewId].zoom_x;
    zoom_dy = zoom[1] - viz_state.zoom.zoom_data[viewId].zoom_y;
  }

  viz_state.zoom.zoom_data.total_zoom.x += zoom_dx;
  viz_state.zoom.zoom_data.total_zoom.y += zoom_dy;

  // keep zoom within bounds
  viz_state.zoom.zoom_data.total_zoom.x = Math.max(
    0,
    viz_state.zoom.zoom_data.total_zoom.x
  );
  viz_state.zoom.zoom_data.total_zoom.y = Math.max(
    0,
    viz_state.zoom.zoom_data.total_zoom.y
  );

  // console.log('differential zooms', zoom_dy)
  // console.log(viewId)
  // console.log('data', viz_state.zoom.zoom_data.matrix.zoom_y.toFixed(2))

  const new_zoom = [
    viz_state.zoom.zoom_data.total_zoom.x,
    viz_state.zoom.zoom_data.total_zoom.y,
  ];
  // console.log('new_zoom ', new_zoom)
  // console.log('   ')

  let zoom_curated_x = Math.max(0, new_zoom[0]);
  let zoom_curated_y = Math.max(0, new_zoom[1]);

  // delay zoom based on row/col ratio
  if (viz_state.zoom.major_zoom_axis === 'X') {
    zoom_curated_y = zoom_curated_x - viz_state.zoom.zoom_delay;
  } else if (viz_state.zoom.major_zoom_axis === 'Y') {
    zoom_curated_x = zoom_curated_y - viz_state.zoom.zoom_delay;
  }

  // keep zoom within bounds
  zoom_curated_x = Math.max(0, zoom_curated_x);
  zoom_curated_y = Math.max(0, zoom_curated_y);

  // Composition: pin X so columns/datasets always stay fully visible,
  // regardless of any accumulated horizontal zoom/pan gesture.
  if (viz_state.mat.viz_mode === 'composition') {
    zoom_curated_x = viz_state.zoom.ini_zoom_x;
  }

  const current_matrix_pan = viz_state.zoom.zoom_data.matrix;
  const target_x =
    viewId === 'rows' || viewId === 'dendro_rows'
      ? current_matrix_pan.pan_x
      : target[0];
  const target_y =
    viewId === 'cols' || viewId === 'dendro_cols'
      ? current_matrix_pan.pan_y
      : target[1];

  let pan_curated_x = curate_pan_x(target_x, zoom_curated_x, viz_state);
  const pan_curated_y = curate_pan_y(target_y, zoom_curated_y, viz_state);

  if (viz_state.mat.viz_mode === 'composition') {
    pan_curated_x = viz_state.zoom.ini_pan_x;
  }

  const zoom_curated = [zoom_curated_x, zoom_curated_y];
  const pan_curated = [pan_curated_x, pan_curated_y];

  const global_view_state = redefine_global_view_state(
    viz_state,
    viewId,
    zoom_curated,
    pan_curated
  );

  // update_zoom_data(viz_state, viewId, new_zoom, target)
  update_zoom_data(viz_state, viewId, zoom_curated, pan_curated);

  let zoom_factor;
  if (viz_state.zoom.major_zoom_axis === 'X') {
    zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x);
  } else if (viz_state.zoom.major_zoom_axis === 'Y') {
    zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_y);
  } else if (viz_state.zoom.major_zoom_axis === 'all') {
    zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.matrix.zoom_x);
  }

  if (viz_state.mat.viz_mode === 'composition') {
    // Row label size is deliberately fixed (not rescaled with zoom) in
    // composition mode, so zooming in on rows grows a segment relative to its
    // label instead of both growing together — see `compute_row_label_visibility`
    // in `composition_data.js`. Re-run the fit check every tick so labels
    // reveal themselves as soon as there's room.
    refresh_row_label_visibility(layers_mat, viz_state);
  } else {
    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
      getSize: get_zoomed_axis_label_font_size(
        viz_state,
        'row',
        viz_state.zoom.zoom_data.matrix.zoom_y
      ),
    });
  }

  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    getSize: get_zoomed_axis_label_font_size(
      viz_state,
      'col',
      viz_state.zoom.zoom_data.matrix.zoom_x
    ),
    updateTriggers: {
      getPixelOffset: viz_state.zoom.zoom_data.matrix.zoom_x,
    },
  });

  let zoom_mode;
  if (viz_state.mat.viz_mode === 'composition') {
    // Permanent lock, unlike the shape-driven aspect-ratio delay below (which
    // always eventually unlocks to 'all' once zoomed in enough).
    zoom_mode = 'Y';
  } else if (viz_state.zoom.major_zoom_axis !== 'all') {
    zoom_mode =
      zoom_factor < viz_state.zoom.switch_ratio
        ? viz_state.zoom.major_zoom_axis
        : 'all';
  } else {
    zoom_mode = 'all';
  }

  // Recreate each view with updated zoomAxis in controller
  // Preserve controller: false for static views (attribute labels)
  viz_state.views.views_list = viz_state.views.views_list.map((view) => {
    // Don't modify controller for static views
    if (view.props.controller === false) {
      return view;
    }
    return new OrthographicView({
      ...view.props,
      controller: {
        ...view.props.controller,
        doubleClickZoom: false,
        dragPan: !viz_state.crop?.active,
        scrollZoom: true,
        inertia: true,
        zoomAxis: zoom_mode,
      },
    });
  });

  deck_mat.setProps({
    viewState: global_view_state,
    layers: get_mat_layers_list(layers_mat, {
      snap_annotations: viz_state.crop?._snap_annotation_transitions,
    }),
    views: viz_state.views.views_list,
  });
};
