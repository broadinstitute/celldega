import { ini_deck, set_views_prop } from '../deck-gl/core/deck_ist';
import {
  create_landmark_views,
  landmark_panel_width,
  side_for_viewport_id,
  view_id_for_side,
  initial_view_state_for_centroids,
} from '../deck-gl/core/landmark_viewports';
import {
  ini_landmark_cell_layer,
  centroid_rows_from_parquet,
  cluster_categories,
} from '../deck-gl/layers/landmark_cell_layer';
import {
  ini_landmark_marker_layer,
  features_to_geojson,
  geojson_to_features,
} from '../deck-gl/layers/landmark_marker_layer';
import { objects_from_parquet } from '../read_parquet/objects_from_parquet';
import { make_landmark_dropdown } from '../ui/landmark_dropdown';
import {
  make_landmark_toolbar,
  set_mark_button_active,
  set_del_button_visible,
  register_landmark_keyboard_shortcuts,
  make_cluster_legend,
} from '../ui/landmark_ui';

const SIDES = ['a', 'b'];

const decode_centroids = async (model, side) => {
  const bytes = model.get(`centroids_parquet_${side}`);
  if (!bytes || bytes.byteLength === 0) return [];
  const parsed = await objects_from_parquet(bytes, 'cell_id');
  return centroid_rows_from_parquet(parsed);
};

export const landmark_ist = async (model, el) => {
  el.innerHTML = '';

  const width = model.get('width') || el.clientWidth || 900;
  const height = model.get('height') || 600;
  const panel_width = landmark_panel_width(width);

  const root_container = document.createElement('div');
  root_container.className = 'landmark-root';
  el.appendChild(root_container);

  const header_row = document.createElement('div');
  header_row.style.display = 'flex';
  header_row.style.justifyContent = 'space-between';
  header_row.style.width = `${width}px`;

  const legend_row = document.createElement('div');
  legend_row.style.display = 'flex';
  legend_row.style.justifyContent = 'space-between';
  legend_row.style.width = `${width}px`;

  const panels_row = document.createElement('div');
  panels_row.style.width = `${width}px`;
  panels_row.style.height = `${height}px`;

  const state = {
    mark_mode: false,
    draft: { a: null, b: null },
    selected_label: null,
    next_label: model.get('next_landmark_label') || 1,
    rows: { a: [], b: [] },
    features: { a: [], b: [] },
    highlight_cluster: { a: null, b: null },
  };

  const [rows_a, rows_b] = await Promise.all(
    SIDES.map((side) => decode_centroids(model, side))
  );
  state.rows.a = rows_a;
  state.rows.b = rows_b;
  state.features.a = geojson_to_features(model.get('landmark_geojson_a'));
  state.features.b = geojson_to_features(model.get('landmark_geojson_b'));

  const views = create_landmark_views(width, height);
  const deck_ist = ini_deck(panels_row, width, height);
  set_views_prop(deck_ist, views);

  const combined_features = (side) => {
    const committed = state.features[side].filter((f) => !f.properties.draft);
    return state.draft[side] ? [...committed, state.draft[side]] : committed;
  };

  const build_layers = () =>
    SIDES.flatMap((side) => [
      ini_landmark_cell_layer(side, state.rows[side], {
        highlight_cluster: state.highlight_cluster[side],
      }),
      ini_landmark_marker_layer(side, combined_features(side), {
        selected_label: state.selected_label,
      }),
    ]);

  const refresh = () => {
    deck_ist.setProps({ layers: build_layers() });
  };

  const layer_filter = ({ layer, viewport }) => {
    const side = side_for_viewport_id(viewport.id);
    return side ? layer.id.endsWith(`-${side}`) : true;
  };

  deck_ist.setProps({
    layerFilter: layer_filter,
    initialViewState: {
      [view_id_for_side('a')]: initial_view_state_for_centroids(
        state.rows.a,
        panel_width,
        height
      ),
      [view_id_for_side('b')]: initial_view_state_for_centroids(
        state.rows.b,
        panel_width,
        height
      ),
    },
    layers: build_layers(),
  });

  // --- MARK / SAVE / DEL state machine --------------------------------------

  const sync_side_to_model = (side) => {
    model.set(`landmark_geojson_${side}`, {
      type: 'FeatureCollection',
      features: [],
    });
    model.set(
      `landmark_geojson_${side}`,
      features_to_geojson(state.features[side])
    );
    model.save_changes();
  };

  const toolbar = make_landmark_toolbar({
    on_mark_toggle: () => set_mark_mode(!state.mark_mode),
    on_save: () => save_pair(),
    on_delete: () => delete_selected(),
  });

  function set_mark_mode(active) {
    state.mark_mode = active;
    set_mark_button_active(toolbar.buttons, active);
    if (!active) {
      state.draft.a = null;
      state.draft.b = null;
      refresh();
    }
  }

  function place_draft(side, coordinate) {
    state.draft[side] = {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [coordinate[0], coordinate[1]] },
      properties: { label: String(state.next_label), draft: true },
    };
    refresh();
  }

  function cancel_draft() {
    state.draft.a = null;
    state.draft.b = null;
    refresh();
  }

  function save_pair() {
    if (!state.draft.a || !state.draft.b) return;
    const label = String(state.next_label);
    SIDES.forEach((side) => {
      state.features[side].push({
        type: 'Feature',
        geometry: state.draft[side].geometry,
        properties: { label, draft: false },
      });
      state.draft[side] = null;
    });
    state.next_label += 1;
    refresh();
    SIDES.forEach(sync_side_to_model);
  }

  function clear_selection() {
    if (!state.selected_label) return;
    state.selected_label = null;
    set_del_button_visible(toolbar.buttons, false);
    refresh();
  }

  function select_landmark(label) {
    state.selected_label = label;
    set_del_button_visible(toolbar.buttons, true);
    refresh();
  }

  function delete_selected() {
    if (!state.selected_label) return;
    const label = state.selected_label;
    SIDES.forEach((side) => {
      state.features[side] = state.features[side].filter(
        (f) => f.properties.label !== label
      );
    });
    state.selected_label = null;
    set_del_button_visible(toolbar.buttons, false);
    refresh();
    SIDES.forEach(sync_side_to_model);
  }

  // --- Pointer interaction ---------------------------------------------------

  let dragging = null; // { side, label, is_draft }

  const handle_click = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side) return;

    if (info.object && info.layer?.id?.startsWith('landmark-icon-')) {
      select_landmark(info.object.properties.label);
      return;
    }

    if (state.selected_label) {
      clear_selection();
      return;
    }

    if (state.mark_mode && !state.draft[side] && info.coordinate) {
      place_draft(side, info.coordinate);
    }
  };

  const handle_drag_start = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side || !info.object || !info.layer?.id?.startsWith('landmark-icon-'))
      return;
    dragging = {
      side,
      label: info.object.properties.label,
      is_draft: info.object.properties.draft,
    };
  };

  const handle_drag = (info) => {
    if (!dragging || !info.coordinate) return;
    const { side, label, is_draft } = dragging;
    const coordinates = [info.coordinate[0], info.coordinate[1]];
    if (is_draft) {
      state.draft[side] = {
        ...state.draft[side],
        geometry: { type: 'Point', coordinates },
      };
    } else {
      state.features[side] = state.features[side].map((f) =>
        f.properties.label === label
          ? { ...f, geometry: { type: 'Point', coordinates } }
          : f
      );
    }
    refresh();
  };

  const handle_drag_end = () => {
    if (dragging && !dragging.is_draft) {
      sync_side_to_model(dragging.side);
    }
    dragging = null;
  };

  deck_ist.setProps({
    onClick: handle_click,
    onDragStart: handle_drag_start,
    onDrag: handle_drag,
    onDragEnd: handle_drag_end,
    getCursor: ({ isDragging }) => {
      if (isDragging) return 'grabbing';
      return state.mark_mode ? 'crosshair' : 'grab';
    },
  });

  const cleanup_shortcuts = register_landmark_keyboard_shortcuts({
    on_mark_toggle: () => set_mark_mode(!state.mark_mode),
    on_save: () => save_pair(),
    on_cancel: () => {
      if (state.draft.a || state.draft.b) {
        cancel_draft();
      } else {
        set_mark_mode(false);
      }
      clear_selection();
    },
    on_delete: () => delete_selected(),
  });

  // --- Slice-swap dropdowns ---------------------------------------------------

  const slice_ids = model.get('slice_ids') || [];
  const slice_labels = model.get('slice_labels') || {};

  const make_side_dropdown = (side) =>
    make_landmark_dropdown(
      slice_ids,
      slice_labels,
      model.get(`slice_id_${side}`),
      (value) => {
        model.set(`slice_id_${side}`, value);
        model.save_changes();
      }
    );

  const header_a = document.createElement('div');
  header_a.appendChild(make_side_dropdown('a'));
  const header_b = document.createElement('div');
  header_b.appendChild(make_side_dropdown('b'));
  header_row.append(header_a, header_b);

  // --- Cluster legends ---------------------------------------------------------

  const rebuild_legend = () => {
    legend_row.innerHTML = '';
    SIDES.forEach((side) => {
      const categories = cluster_categories(state.rows[side]);
      if (!categories.length) return;
      legend_row.appendChild(
        make_cluster_legend(categories, (cluster) => {
          state.highlight_cluster[side] = cluster;
          refresh();
        })
      );
    });
  };
  rebuild_legend();

  root_container.append(header_row, toolbar.container, legend_row, panels_row);

  // --- React to Python-driven slice swaps ---------------------------------------

  const on_side_swapped = async (side) => {
    state.rows[side] = await decode_centroids(model, side);
    state.features[side] = geojson_to_features(
      model.get(`landmark_geojson_${side}`)
    );
    state.draft[side] = null;
    state.highlight_cluster[side] = null;
    rebuild_legend();
    refresh();
  };

  model.on('change:slice_id_a', () => on_side_swapped('a'));
  model.on('change:slice_id_b', () => on_side_swapped('b'));

  return {
    finalize: () => {
      cleanup_shortcuts();
      deck_ist.finalize();
    },
  };
};
