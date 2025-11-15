import { LinearInterpolator, PolygonLayer } from 'deck.gl';

import { sync_selected_genes } from '../../global_variables/selected_genes';

import { curate_pan_x, curate_pan_y } from './curate_pan';
import { get_mat_layers_list } from './matrix_layers';
import { redefine_global_view_state } from './redefine_global_view_state';
import { update_zoom_data } from './zoom';

const DENDRO_AXES = ['row', 'col'];
const DEFAULT_FILL_COLOR = [0, 0, 0, 90];
const FOCUSED_FILL_COLOR = [0, 0, 0, 180];
const DOUBLE_CLICK_DELAY = 250;
const DENDRO_FOCUS_TRANSITION = 650;
const MAX_FOCUS_ZOOM = 7;

const ease_out_cubic = (t) => 1 - Math.pow(1 - t, 3);

const ensure_click_tracking = (viz_state) => {
  if (!viz_state.dendro.clicks) {
    viz_state.dendro.clicks = { row: 0, col: 0 };
  }

  if (!viz_state.dendro.click_timeouts) {
    viz_state.dendro.click_timeouts = { row: null, col: null };
  }

  if (!viz_state.dendro.double_click_state) {
    viz_state.dendro.double_click_state = { row: null, col: null };
  }
};

const apply_view_state_transition = (view_state) => {
  const transition_props = () => ({
    transitionDuration: DENDRO_FOCUS_TRANSITION,
    transitionEasing: ease_out_cubic,
    transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
  });

  return Object.fromEntries(
    Object.entries(view_state).map(([key, value]) => [
      key,
      { ...value, ...transition_props() },
    ])
  );
};

const compute_cluster_zoom = (matrix_span, cluster_span, min_unit) => {
  const effective_span = Math.min(matrix_span, Math.max(cluster_span, min_unit));

  const zoom = Math.log2(matrix_span / Math.max(effective_span, 1e-6));

  return Math.min(Math.max(zoom, 0), MAX_FOCUS_ZOOM);
};

const animate_focus_to_cluster = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygonProps
) => {
  if (!polygonProps) {
    return;
  }

  const is_row_axis = axis === 'row';
  const matrix_span = is_row_axis
    ? viz_state.viz.mat_height
    : viz_state.viz.mat_width;
  const min_unit = is_row_axis
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;

  const current_zoom_x = viz_state.zoom.zoom_data.matrix.zoom_x;
  const current_zoom_y = viz_state.zoom.zoom_data.matrix.zoom_y;

  const cluster_span = Math.max(
    Math.abs((polygonProps.pos_bot ?? 0) - (polygonProps.pos_top ?? 0)),
    min_unit
  );

  const target_zoom = compute_cluster_zoom(matrix_span, cluster_span, min_unit);

  const zoom_curated = [
    is_row_axis ? current_zoom_x : target_zoom,
    is_row_axis ? target_zoom : current_zoom_y,
  ];

  const cluster_center =
    ((polygonProps.pos_top ?? 0) + (polygonProps.pos_bot ?? 0)) / 2;

  const existing_pan = viz_state.zoom.zoom_data.matrix;

  const desired_pan = {
    x: is_row_axis ? existing_pan.pan_x : cluster_center,
    y: is_row_axis ? cluster_center : existing_pan.pan_y,
  };

  const pan_curated = [
    curate_pan_x(desired_pan.x, zoom_curated[0], viz_state),
    curate_pan_y(desired_pan.y, zoom_curated[1], viz_state),
  ];

  const view_id = is_row_axis ? 'dendro_rows' : 'dendro_cols';

  const global_view_state = redefine_global_view_state(
    viz_state,
    view_id,
    zoom_curated,
    pan_curated
  );

  update_zoom_data(viz_state, view_id, zoom_curated, pan_curated);

  viz_state.zoom.zoom_data.total_zoom.x = zoom_curated[0];
  viz_state.zoom.zoom_data.total_zoom.y = zoom_curated[1];

  deck_mat.setProps({
    viewState: apply_view_state_transition(global_view_state),
    layers: get_mat_layers_list(layers_mat),
  });
};

const animate_focus_reset = (deck_mat, layers_mat, viz_state) => {
  const default_zoom = [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y];
  const default_pan = [viz_state.zoom.ini_pan_x, viz_state.zoom.ini_pan_y];

  const global_view_state = redefine_global_view_state(
    viz_state,
    'matrix',
    default_zoom,
    default_pan
  );

  update_zoom_data(viz_state, 'matrix', default_zoom, default_pan);

  viz_state.zoom.zoom_data.total_zoom.x = default_zoom[0];
  viz_state.zoom.zoom_data.total_zoom.y = default_zoom[1];

  deck_mat.setProps({
    viewState: apply_view_state_transition(global_view_state),
    layers: get_mat_layers_list(layers_mat),
  });
};

const get_current_focus = (viz_state) => {
  const store_focus =
    viz_state?.obs_store?.focused_dendro &&
    typeof viz_state.obs_store.focused_dendro.get === 'function'
      ? viz_state.obs_store.focused_dendro.get()
      : null;

  return store_focus ?? viz_state.dendro?.active_polygon ?? null;
};

const apply_dendro_focus = (deck_mat, layers_mat, viz_state, focus) => {
  const normalized_focus = focus
    ? { axis: focus.axis, name: focus.name }
    : null;

  let didUpdate = false;

  DENDRO_AXES.forEach((targetAxis) => {
    if (!viz_state.dendro.polygons[targetAxis]) {
      return;
    }

    const updatedPolygons = viz_state.dendro.polygons[targetAxis].map(
      (polygon) => {
        const is_focused =
          !!normalized_focus &&
          polygon.properties.axis === normalized_focus.axis &&
          polygon.properties.name === normalized_focus.name;

        if (polygon.properties.is_focused === is_focused) {
          return polygon;
        }

        didUpdate = true;

        return {
          ...polygon,
          properties: {
            ...polygon.properties,
            is_focused,
          },
        };
      }
    );

    viz_state.dendro.polygons[targetAxis] = updatedPolygons;

    if (layers_mat[`${targetAxis}_dendro_layer`]) {
      layers_mat[`${targetAxis}_dendro_layer`] = layers_mat[
        `${targetAxis}_dendro_layer`
      ].clone({
        data: updatedPolygons,
      });
    }
  });

  viz_state.dendro.active_polygon = normalized_focus;

  if (viz_state.obs_store?.focused_dendro) {
    const focus_value = normalized_focus ? { ...normalized_focus } : null;
    viz_state.obs_store.focused_dendro.set(focus_value);
  }

  if (didUpdate && typeof deck_mat?.setProps === 'function') {
    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  }
};

export const ini_dendro_layer = (layers_mat, viz_state, axis) => {
  const inst_layer = new PolygonLayer({
    id: `${axis}-dendro-layer`,
    data: viz_state.dendro.polygons[axis],
    getPolygon: (d) => d.coordinates,
    getFillColor: (d) => {
      if (d.properties.is_focused) {
        return FOCUSED_FILL_COLOR;
      }

      if (Array.isArray(d.properties.fill_color)) {
        return d.properties.fill_color;
      }

      return DEFAULT_FILL_COLOR;
    },
    getLineColor: [255, 255, 255, 255],
    lineWidthMinPixels: 0,
    pickable: true,
    antialiasing: false,
    // autoHighlight: true, // Highlight on hover
    // onHover: ({ object }) => console.log(object?.properties.name), // Hover info
  });

  return inst_layer;
};

export const update_dendro_layer_data = (layers_mat, viz_state, axis) => {
  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      data: viz_state.dendro.polygons[axis],
    }
  );
};

export const toggle_dendro_layer_visibility = (layers_mat, viz_state, axis) => {
  // if viz_state.order.curent[axis] is 'clust' then the dendrogram is visible
  let is_visible = false;
  if (viz_state.order.current[axis] === 'clust') {
    is_visible = true;
  }

  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      // visible: !layers_mat[axis + '_dendro_layer'].visible,
      visible: is_visible,
    }
  );
};

const focus_dendro_polygon = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  polygon_name,
  options = {}
) => {
  const { allow_toggle = true } = options;

  const previous_focus = get_current_focus(viz_state);

  if (
    allow_toggle &&
    previous_focus &&
    previous_focus.axis === axis &&
    previous_focus.name === polygon_name
  ) {
    apply_dendro_focus(deck_mat, layers_mat, viz_state, null);
    return false;
  }

  apply_dendro_focus(deck_mat, layers_mat, viz_state, {
    axis,
    name: polygon_name,
  });

  return true;
};

const dendro_layer_on_click = (
  event,
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  ensure_click_tracking(viz_state);

  const clicked_name = event.object.properties.name;
  const current_focus = get_current_focus(viz_state);
  const was_active_before_click =
    current_focus &&
    current_focus.axis === axis &&
    current_focus.name === clicked_name;

  viz_state.dendro.clicks[axis] += 1;

  viz_state.click.type = `${axis}_dendro`;

  viz_state.click.value = {
    name: clicked_name,
    selected_names: event.object.properties.all_names,
  };

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
  }

  if (axis === 'row') {
    sync_selected_genes(viz_state, event.object.properties.all_names);
  }

  if (typeof viz_state.custom_callbacks[`${axis}_dendro`] === 'function') {
    viz_state.custom_callbacks[`${axis}_dendro`](
      event.object.properties.all_names
    );
  }

  const double_click_state = {
    name: clicked_name,
    was_active_before_click,
  };

  if (viz_state.dendro.clicks[axis] === 1) {
    viz_state.dendro.double_click_state[axis] = double_click_state;

    focus_dendro_polygon(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      clicked_name
    );

    viz_state.dendro.click_timeouts[axis] = setTimeout(() => {
      viz_state.dendro.clicks[axis] = 0;
      viz_state.dendro.click_timeouts[axis] = null;
      viz_state.dendro.double_click_state[axis] = null;
    }, DOUBLE_CLICK_DELAY);
  } else if (viz_state.dendro.clicks[axis] === 2) {
    if (viz_state.dendro.click_timeouts[axis]) {
      clearTimeout(viz_state.dendro.click_timeouts[axis]);
      viz_state.dendro.click_timeouts[axis] = null;
    }

    viz_state.dendro.clicks[axis] = 0;

    const prior_state = viz_state.dendro.double_click_state[axis];
    viz_state.dendro.double_click_state[axis] = null;

    const initiated_from_active =
      prior_state &&
      prior_state.name === clicked_name &&
      prior_state.was_active_before_click;

    if (initiated_from_active) {
      apply_dendro_focus(deck_mat, layers_mat, viz_state, null);
      animate_focus_reset(deck_mat, layers_mat, viz_state);
      return;
    }

    focus_dendro_polygon(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      clicked_name,
      { allow_toggle: false }
    );

    animate_focus_to_cluster(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      event.object.properties
    );
  }
};

export const set_dendro_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state,
  axis
) => {
  layers_mat[`${axis}_dendro_layer`] = layers_mat[`${axis}_dendro_layer`].clone(
    {
      onClick: (event) =>
        dendro_layer_on_click(event, deck_mat, layers_mat, viz_state, axis),
    }
  );
};
