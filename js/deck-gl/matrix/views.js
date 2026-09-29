import { OrthographicController, OrthographicView } from 'deck.gl';

import {
  get_axis_display_count,
  get_default_pan,
  get_default_pan_y,
} from '../../matrix/crop_filter';

export const DENDRO_TREE_VIEW_IDS = new Set([
  'dendro_tree_backdrop',
  'dendro_tree_rows',
  'dendro_tree_cols',
  'dendro_tree_foreground',
]);

const matrix_view_bounds = (viz_state) => ({
  x: `${viz_state.viz.row_region + viz_state.viz.label_buffer}px`,
  y: `${viz_state.viz.col_region + viz_state.viz.label_buffer}px`,
  width: `${viz_state.viz.mat_width}px`,
  height: `${viz_state.viz.mat_height}px`,
});

// A controller is required for deck.gl to interpolate programmatic view-state
// transitions. Let pointer events pass through so the existing matrix
// controller remains the sole interactive camera beneath these views.
class TransitionOnlyOrthographicController extends OrthographicController {
  handleEvent() {
    return false;
  }
}

const transition_only_controller = {
  type: TransitionOnlyOrthographicController,
  scrollZoom: false,
  dragPan: false,
  dragRotate: false,
  touchZoom: false,
  touchRotate: false,
  doubleClickZoom: false,
  keyboard: false,
  inertia: false,
};

/**
 * Views used only while the temporary full-tree preview is visible. The two
 * static passes keep the backdrop, cut region, and caption screen-fixed. The
 * branch passes inherit exactly one matrix camera axis.
 */
export const get_dendro_tree_views = (viz_state) => {
  const bounds = matrix_view_bounds(viz_state);
  return [
    new OrthographicView({
      id: 'dendro_tree_backdrop',
      viewState: 'dendro_tree_static',
      ...bounds,
      controller: false,
    }),
    new OrthographicView({
      id: 'dendro_tree_rows',
      ...bounds,
      controller: transition_only_controller,
    }),
    new OrthographicView({
      id: 'dendro_tree_cols',
      ...bounds,
      controller: transition_only_controller,
    }),
    new OrthographicView({
      id: 'dendro_tree_foreground',
      viewState: 'dendro_tree_static',
      ...bounds,
      controller: false,
    }),
  ];
};

export const without_dendro_tree_views = (views) =>
  views.filter((view) => !DENDRO_TREE_VIEW_IDS.has(view.id));

export const with_dendro_tree_views = (views, viz_state) => [
  ...without_dendro_tree_views(views),
  ...get_dendro_tree_views(viz_state),
];

export const get_dendro_tree_view_states = (viz_state, zoom, pan) => ({
  dendro_tree_static: {
    target: [viz_state.viz.mat_width / 2, viz_state.viz.mat_height / 2],
    zoom: [0, 0],
  },
  // Row leaves follow matrix Y; linkage distance stays fitted to screen X.
  dendro_tree_rows: {
    target: [viz_state.viz.mat_width / 2, pan[1]],
    zoom: [0, zoom[1]],
  },
  // Column leaves follow matrix X; linkage distance stays fitted to screen Y.
  dendro_tree_cols: {
    target: [pan[0], viz_state.viz.mat_height / 2],
    zoom: [zoom[0], 0],
  },
});

export const ini_views = (viz_state) => {
  let switch_ratio;
  const drag_pan_enabled = !viz_state.crop?.active;
  const row_count = get_axis_display_count(viz_state, 'row');
  const col_count = get_axis_display_count(viz_state, 'col');

  if (viz_state.mat.viz_mode === 'composition') {
    // Composition: columns (datasets/samples) should always stay fully
    // visible; only rows (population detail) are zoomable. See the matching
    // permanent lock in on_view_state_change.js — this shape-driven
    // major/minor axis system otherwise always eventually unlocks to 'all'.
    viz_state.zoom.major_zoom_axis = 'Y';
    viz_state.zoom.minor_zoom_axis = 'none';
    switch_ratio = 1;
  } else if (row_count > col_count) {
    viz_state.zoom.major_zoom_axis = 'Y';
    viz_state.zoom.minor_zoom_axis = 'X';
    switch_ratio = row_count / col_count;
  } else if (row_count < col_count) {
    viz_state.zoom.major_zoom_axis = 'X';
    viz_state.zoom.minor_zoom_axis = 'Y';
    switch_ratio = col_count / row_count;
  } else if (row_count === col_count) {
    viz_state.zoom.major_zoom_axis = 'all';
    viz_state.zoom.minor_zoom_axis = 'none';
    switch_ratio = 1;
  }

  viz_state.zoom.switch_ratio = switch_ratio;
  viz_state.zoom.zoom_delay = Math.log2(switch_ratio);

  let views_list = [
    new OrthographicView({
      id: 'matrix',
      x: `${viz_state.viz.row_region + viz_state.viz.label_buffer}px`,
      y: `${viz_state.viz.col_region + viz_state.viz.label_buffer}px`,
      width: `${viz_state.viz.mat_width}px`,
      height: `${viz_state.viz.mat_height}px`,
      controller: {
        scrollZoom: true,
        dragPan: drag_pan_enabled,
        inertia: true,
        zoomAxis: viz_state.zoom.major_zoom_axis,
        doubleClickZoom: false,
      },
    }),

    new OrthographicView({
      id: 'rows',
      x: '0px',
      y: `${viz_state.viz.col_region + viz_state.viz.label_buffer}px`,
      width: `${viz_state.viz.row_region}px`,
      height: `${viz_state.viz.mat_height}px`,
      controller: {
        scrollZoom: true,
        dragPan: drag_pan_enabled,
        inertia: false,
        zoomAxis: viz_state.zoom.major_zoom_axis,
        doubleClickZoom: false,
      },
    }),

    new OrthographicView({
      id: 'cols',
      x: `${viz_state.viz.row_region + viz_state.viz.label_buffer}px`,
      y: '0px',
      width: `${viz_state.viz.mat_width}px`,
      height: `${viz_state.viz.col_region}px`,
      controller: {
        scrollZoom: true,
        dragPan: drag_pan_enabled,
        inertia: false,
        zoomAxis: viz_state.zoom.major_zoom_axis,
        doubleClickZoom: false,
      },
    }),

    // Static view for row attribute labels (top-left corner, no zoom/pan)
    new OrthographicView({
      id: 'row_attr_labels',
      x: '0px',
      y: '0px',
      width: `${viz_state.viz.row_region}px`,
      height: `${viz_state.viz.col_region}px`,
      controller: false,
    }),

    // Static view for column attribute labels (right side, aligned with dendrogram)
    new OrthographicView({
      id: 'col_attr_labels',
      x: `${viz_state.viz.row_region + viz_state.viz.label_buffer + viz_state.viz.mat_width}px`,
      y: '0px',
      width: `${viz_state.viz.dendrogram_width + 60}px`,
      height: `${viz_state.viz.col_region}px`,
      controller: false,
    }),

    // New Dendrogram Views

    // Dendrogram under the matrix
    new OrthographicView({
      id: 'dendro_cols',
      x: `${viz_state.viz.row_region + viz_state.viz.label_buffer}px`,
      y: `${viz_state.viz.col_region + viz_state.viz.label_buffer + viz_state.viz.mat_height}px`,
      width: `${viz_state.viz.mat_width}px`,
      height: `${viz_state.viz.dendrogram_width}px`,
      controller: {
        scrollZoom: true,
        dragPan: drag_pan_enabled,
        inertia: false,
        zoomAxis: viz_state.zoom.major_zoom_axis,
        doubleClickZoom: false,
      },
    }),

    // Dendrogram to the right of the matrix
    new OrthographicView({
      id: 'dendro_rows',
      x: `${viz_state.viz.row_region + viz_state.viz.label_buffer + viz_state.viz.mat_width}px`,
      y: `${viz_state.viz.col_region + viz_state.viz.label_buffer}px`,
      width: `${viz_state.viz.dendrogram_width}px`,
      height: `${viz_state.viz.mat_height}px`,
      controller: {
        scrollZoom: true,
        dragPan: drag_pan_enabled,
        inertia: false,
        zoomAxis: viz_state.zoom.major_zoom_axis,
        doubleClickZoom: false,
      },
    }),
  ];

  // Rebuilding controller views (for example during a focus transition) must
  // not reopen a hidden preview, but an already-mounted preview should remain
  // synchronized through that rebuild, including its short fade-out window.
  if (viz_state.dendro?.tree_overlay?.has_views()) {
    views_list = with_dendro_tree_views(views_list, viz_state);
  }

  viz_state.views = {};

  viz_state.views.views_list = views_list;
};

export const ini_view_state = (viz_state) => {
  const default_pan = get_default_pan(viz_state);
  const default_pan_y = get_default_pan_y(viz_state);

  const globalViewState = {
    matrix: {
      target: default_pan,
      zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
    },
    rows: {
      target: [viz_state.viz.label_row_x, default_pan_y],
      zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
    },
    cols: {
      target: [default_pan[0], viz_state.viz.label_col_y],
      zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
    },
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
    dendro_rows: {
      target: [viz_state.viz.label_row_x, default_pan_y],
      zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
    },
    dendro_cols: {
      target: [default_pan[0], viz_state.viz.label_col_y],
      zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
    },
    ...get_dendro_tree_view_states(
      viz_state,
      [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
      default_pan
    ),
  };

  return globalViewState;
};
