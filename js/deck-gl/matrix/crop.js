import { LinearInterpolator } from 'deck.gl';

import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { update_zoom_data } from './zoom';

const CROP_MIN_DRAG_PX = 8;
const CROP_TRANSITION_MS = 450;

const ease_out_cubic = (t) => 1 - Math.pow(1 - t, 3);

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const get_matrix_screen_bounds = (viz_state) => {
  const left = viz_state.viz.row_region + viz_state.viz.label_buffer;
  const top = viz_state.viz.col_region + viz_state.viz.label_buffer;

  return {
    left,
    top,
    right: left + viz_state.viz.mat_width,
    bottom: top + viz_state.viz.mat_height,
  };
};

const get_matrix_world_bounds = (viz_state) => ({
  min_x: 0,
  max_x: viz_state.viz.mat_width,
  min_y: viz_state.viz.row_offset,
  max_y: viz_state.viz.mat_height + viz_state.viz.row_offset,
});

const clamp_screen_point = (viz_state, x, y) => {
  const bounds = get_matrix_screen_bounds(viz_state);

  return [
    clamp(x, bounds.left, bounds.right),
    clamp(y, bounds.top, bounds.bottom),
  ];
};

const clamp_world_point = (viz_state, coord) => {
  const bounds = get_matrix_world_bounds(viz_state);

  return [
    clamp(coord[0], bounds.min_x, bounds.max_x),
    clamp(coord[1], bounds.min_y, bounds.max_y),
  ];
};

const get_matrix_viewport = (deck_mat) =>
  deck_mat.viewManager
    ?.getViewports()
    ?.find((viewport) => viewport.id === 'matrix');

const screen_to_matrix_world = (deck_mat, viz_state, x, y) => {
  const viewport = get_matrix_viewport(deck_mat);
  if (!viewport) return null;

  const [clamped_x, clamped_y] = clamp_screen_point(viz_state, x, y);
  const coordinate = viewport.unproject([clamped_x, clamped_y]);

  return Array.isArray(coordinate)
    ? clamp_world_point(viz_state, coordinate)
    : null;
};

const set_overlay_bounds = (overlay, start_screen, end_screen) => {
  const left = Math.min(start_screen[0], end_screen[0]);
  const top = Math.min(start_screen[1], end_screen[1]);
  const width = Math.abs(end_screen[0] - start_screen[0]);
  const height = Math.abs(end_screen[1] - start_screen[1]);

  overlay.style.display = 'block';
  overlay.style.left = `${left}px`;
  overlay.style.top = `${top}px`;
  overlay.style.width = `${width}px`;
  overlay.style.height = `${height}px`;
};

const hide_overlay = (overlay) => {
  overlay.style.display = 'none';
  overlay.style.width = '0px';
  overlay.style.height = '0px';
};

const transition_view_state = (view_state) =>
  Object.fromEntries(
    Object.entries(view_state).map(([key, value]) => [
      key,
      {
        ...value,
        transitionDuration: CROP_TRANSITION_MS,
        transitionEasing: ease_out_cubic,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
      },
    ])
  );

const apply_zoom_state = (
  deck_mat,
  layers_mat,
  viz_state,
  zoom_curated,
  pan_curated
) => {
  const global_view_state = redefine_global_view_state(
    viz_state,
    'matrix',
    zoom_curated,
    pan_curated
  );

  update_zoom_data(viz_state, 'matrix', zoom_curated, pan_curated);
  viz_state.zoom.zoom_data.total_zoom.x = zoom_curated[0];
  viz_state.zoom.zoom_data.total_zoom.y = zoom_curated[1];

  deck_mat.setProps({
    viewState: transition_view_state(global_view_state),
    layers: get_mat_layers_list(layers_mat),
  });
};

export const compute_crop_view = (
  viz_state,
  start_coord,
  end_coord,
  options = {}
) => {
  const { preserve_x = false, preserve_y = false } = options;
  const current = viz_state.zoom.zoom_data.matrix;
  const [start_x, start_y] = clamp_world_point(viz_state, start_coord);
  const [end_x, end_y] = clamp_world_point(viz_state, end_coord);

  const min_x = Math.min(start_x, end_x);
  const max_x = Math.max(start_x, end_x);
  const min_y = Math.min(start_y, end_y);
  const max_y = Math.max(start_y, end_y);

  const zoom_x = preserve_x
    ? current.zoom_x
    : Math.max(
        0,
        Math.log2(
          viz_state.viz.mat_width /
            Math.max(max_x - min_x, viz_state.viz.col_offset)
        )
      );

  const zoom_y = preserve_y
    ? current.zoom_y
    : Math.max(
        0,
        Math.log2(
          viz_state.viz.mat_height /
            Math.max(max_y - min_y, viz_state.viz.row_offset)
        )
      );

  const pan_x = preserve_x ? current.pan_x : (min_x + max_x) / 2;
  const pan_y = preserve_y ? current.pan_y : (min_y + max_y) / 2;

  return {
    zoom_curated: [zoom_x, zoom_y],
    pan_curated: [pan_x, pan_y],
  };
};

const refresh_controls = (viz_state) => {
  if (!viz_state.crop?.controls) return;

  viz_state.crop.controls.setActive(viz_state.crop.active);
  viz_state.crop.controls.setUndoEnabled(viz_state.crop.history.length > 0);
};

export const initialize_matrix_crop = (
  deck_mat,
  layers_mat,
  viz_state,
  options = {}
) => {
  viz_state.root.style.position = 'relative';

  const overlay = document.createElement('div');
  overlay.style.position = 'absolute';
  overlay.style.display = 'none';
  overlay.style.pointerEvents = 'none';
  overlay.style.border = '1px solid rgba(56, 109, 241, 0.95)';
  overlay.style.background = 'rgba(56, 109, 241, 0.12)';
  overlay.style.boxSizing = 'border-box';
  overlay.style.zIndex = '2';
  viz_state.root.appendChild(overlay);

  viz_state.crop = {
    active: false,
    drag: null,
    history: [],
    controls: null,
    overlay,
    onModeChange: options.onModeChange || null,
    refreshControls: () => refresh_controls(viz_state),
    setControls: (controls) => {
      viz_state.crop.controls = controls;
      refresh_controls(viz_state);
    },
    setMode: (active) => {
      viz_state.crop.active = active;
      viz_state.crop.drag = null;
      hide_overlay(overlay);
      viz_state.crop.onModeChange?.(active);
      refresh_controls(viz_state);
    },
    toggle: () => {
      viz_state.crop.setMode(!viz_state.crop.active);
    },
    undo: () => {
      const previous = viz_state.crop.history.pop();
      if (!previous) return;

      viz_state.crop.setMode(false);
      apply_zoom_state(
        deck_mat,
        layers_mat,
        viz_state,
        previous.zoom_curated,
        previous.pan_curated
      );
      refresh_controls(viz_state);
    },
    onDragStart: (info) => {
      if (!viz_state.crop.active || info.viewport?.id !== 'matrix') return;

      const start_screen = clamp_screen_point(viz_state, info.x, info.y);
      const start_coord = screen_to_matrix_world(
        deck_mat,
        viz_state,
        info.x,
        info.y
      );

      if (!start_coord) return;

      viz_state.crop.drag = {
        start_screen,
        end_screen: start_screen,
        start_coord,
        end_coord: start_coord,
      };

      set_overlay_bounds(overlay, start_screen, start_screen);
    },
    onDrag: (info) => {
      if (!viz_state.crop.drag) return;

      const end_screen = clamp_screen_point(viz_state, info.x, info.y);
      const end_coord = screen_to_matrix_world(
        deck_mat,
        viz_state,
        info.x,
        info.y
      );

      if (!end_coord) return;

      viz_state.crop.drag.end_screen = end_screen;
      viz_state.crop.drag.end_coord = end_coord;

      set_overlay_bounds(
        overlay,
        viz_state.crop.drag.start_screen,
        viz_state.crop.drag.end_screen
      );
    },
    onDragEnd: (info) => {
      if (!viz_state.crop.drag) return;

      if (info?.x != null && info?.y != null) {
        const end_screen = clamp_screen_point(viz_state, info.x, info.y);
        const end_coord = screen_to_matrix_world(
          deck_mat,
          viz_state,
          info.x,
          info.y
        );

        if (end_coord) {
          viz_state.crop.drag.end_screen = end_screen;
          viz_state.crop.drag.end_coord = end_coord;
        }
      }

      const { start_screen, end_screen, start_coord, end_coord } =
        viz_state.crop.drag;

      viz_state.crop.drag = null;
      hide_overlay(overlay);

      const width = Math.abs(end_screen[0] - start_screen[0]);
      const height = Math.abs(end_screen[1] - start_screen[1]);

      if (width < CROP_MIN_DRAG_PX || height < CROP_MIN_DRAG_PX) {
        return;
      }

      const current = viz_state.zoom.zoom_data.matrix;
      viz_state.crop.history.push({
        zoom_curated: [current.zoom_x, current.zoom_y],
        pan_curated: [current.pan_x, current.pan_y],
      });

      const next_view = compute_crop_view(viz_state, start_coord, end_coord, {
        preserve_x: viz_state.mat.viz_mode === 'composition',
      });

      viz_state.crop.setMode(false);
      apply_zoom_state(
        deck_mat,
        layers_mat,
        viz_state,
        next_view.zoom_curated,
        next_view.pan_curated
      );
      refresh_controls(viz_state);
    },
  };
};
