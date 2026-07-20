import * as d3 from 'd3';

import { ini_deck, set_views_prop } from '../deck-gl/core/deck_ist';
import {
  create_landmark_views,
  landmark_panel_width,
  side_for_viewport_id,
  view_id_for_side,
  centroid_of,
  initial_view_state_for_centroids,
} from '../deck-gl/core/landmark_viewports';
import {
  ini_landmark_cell_layer,
  centroid_rows_from_parquet,
  gene_expression_map_from_parquet,
  cluster_bar_data,
} from '../deck-gl/layers/landmark_cell_layer';
import {
  ini_landmark_marker_layer,
  features_to_geojson,
  geojson_to_features,
} from '../deck-gl/layers/landmark_marker_layer';
import { objects_from_parquet } from '../read_parquet/objects_from_parquet';
import { make_bar_container, make_bar_graph } from '../ui/bar_plot';
import { make_landmark_dropdown } from '../ui/landmark_dropdown';
import {
  make_landmark_toolbar,
  set_mark_button_active,
  set_del_button_visible,
  register_landmark_keyboard_shortcuts,
  make_rotation_slider,
  set_rotation_slider_value,
  make_toggle_button,
  make_range_slider,
  make_gene_search_input,
} from '../ui/landmark_ui';
import { hexToRgb } from '../utils/hexToRgb';
import { build_rotation_state, rotate_point_inverse } from '../utils/rotation';
import { create_scale_bar } from '../utils/scale_bar';

const SIDES = ['a', 'b'];
const GRAY_RGB = [160, 160, 160];
const ACTIVE_RGB = [40, 80, 220];

const decode_centroids = async (model, side) => {
  const bytes = model.get(`centroids_parquet_${side}`);
  if (!bytes || bytes.byteLength === 0) return [];
  const parsed = await objects_from_parquet(bytes, 'cell_id');
  return centroid_rows_from_parquet(parsed);
};

const decode_gene_expression = async (model, side) => {
  const bytes = model.get(`gene_exp_parquet_${side}`);
  if (!bytes || bytes.byteLength === 0) return new Map();
  const parsed = await objects_from_parquet(bytes, 'cell_id');
  return gene_expression_map_from_parquet(parsed);
};

export const landmark_ist = async (model, el) => {
  el.innerHTML = '';

  const width = model.get('width') || el.clientWidth || 900;
  const height = model.get('height') || 600;
  const panel_width = landmark_panel_width(width);
  const column_width = width / 2 - 4;

  const root_container = document.createElement('div');
  root_container.className = 'landmark-root';
  el.appendChild(root_container);

  const shared_toolbar_row = document.createElement('div');
  shared_toolbar_row.style.display = 'flex';
  shared_toolbar_row.style.alignItems = 'center';
  shared_toolbar_row.style.gap = '8px';
  shared_toolbar_row.style.width = `${width}px`;

  const columns_row = document.createElement('div');
  columns_row.style.display = 'flex';
  columns_row.style.width = `${width}px`;
  columns_row.style.gap = '8px';

  const state = {
    mark_mode: false,
    draft: { a: null, b: null },
    selected_label: null,
    active_label: null,
    active_side: 'a',
    next_label: model.get('next_landmark_label') || 1,
    rows: { a: [], b: [] },
    features: { a: [], b: [] },
    highlight_cluster: { a: null, b: null },
    cell_visible: { a: true, b: true },
    cell_radius: { a: 3, b: 3 },
    gene_active: { a: false, b: false },
    gene_exp: { a: new Map(), b: new Map() },
    // Rotation is remembered per *slice id*, not per side, so swapping away
    // and back to a slice restores the angle you left it at.
    rotation_deg_by_slice: {},
    centroid: { a: [0, 0], b: [0, 0] },
    rotation_state: {
      a: build_rotation_state(0, [0, 0]),
      b: build_rotation_state(0, [0, 0]),
    },
    view_states: {},
  };

  const rotation_deg_for_side = (side) =>
    state.rotation_deg_by_slice[model.get(`slice_id_${side}`)] ?? 0;

  const recompute_rotation_state = (side) => {
    state.centroid[side] = centroid_of(state.rows[side]);
    state.rotation_state[side] = build_rotation_state(
      rotation_deg_for_side(side),
      state.centroid[side]
    );
  };

  const [rows_a, rows_b] = await Promise.all(
    SIDES.map((side) => decode_centroids(model, side))
  );
  state.rows.a = rows_a;
  state.rows.b = rows_b;
  SIDES.forEach(recompute_rotation_state);
  state.features.a = geojson_to_features(model.get('landmark_geojson_a'));
  state.features.b = geojson_to_features(model.get('landmark_geojson_b'));

  const panels_wrap = { a: null, b: null }; // filled in once panel wrappers exist, for active-side border styling

  const views = create_landmark_views(width, height);
  const panels_row = document.createElement('div');
  panels_row.style.width = `${width}px`;
  panels_row.style.height = `${height}px`;
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
        rotation_state: state.rotation_state[side],
        visible: state.cell_visible[side],
        radius: state.cell_radius[side],
        gene_active: state.gene_active[side],
        gene_exp_map: state.gene_exp[side],
      }),
      ini_landmark_marker_layer(side, combined_features(side), {
        selected_label: state.selected_label,
        rotation_state: state.rotation_state[side],
      }),
    ]);

  const refresh = () => {
    deck_ist.setProps({ layers: build_layers() });
  };

  const layer_filter = ({ layer, viewport }) => {
    const side = side_for_viewport_id(viewport.id);
    return side ? layer.id.endsWith(`-${side}`) : true;
  };

  state.view_states = {
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
  };

  // Zoom is kept in sync across both views (translation/target is not) —
  // requires staying fully controlled (`viewState`, not `initialViewState`)
  // so a slice swap can also force a camera jump to the new slice's centroid.
  const other_view_id = (view_id) =>
    view_id === view_id_for_side('a')
      ? view_id_for_side('b')
      : view_id_for_side('a');

  const sync_zoom_from = (view_id, zoom) => {
    const partner = other_view_id(view_id);
    state.view_states = {
      ...state.view_states,
      [partner]: { ...state.view_states[partner], zoom },
    };
  };

  const scale_bars = {
    a: create_scale_bar(1, ''),
    b: create_scale_bar(1, ''),
  };
  SIDES.forEach((side) =>
    scale_bars[side].update({
      zoom: state.view_states[view_id_for_side(side)].zoom,
    })
  );

  const handle_view_state_change = ({ viewId, viewState }) => {
    state.view_states = { ...state.view_states, [viewId]: viewState };
    sync_zoom_from(viewId, viewState.zoom);
    deck_ist.setProps({ viewState: state.view_states });
    const side = side_for_viewport_id(viewId);
    if (side) scale_bars[side].update({ zoom: viewState.zoom });
    const partner_side = side_for_viewport_id(other_view_id(viewId));
    if (partner_side) {
      scale_bars[partner_side].update({
        zoom: state.view_states[other_view_id(viewId)].zoom,
      });
    }
  };

  deck_ist.setProps({
    layerFilter: layer_filter,
    viewState: state.view_states,
    onViewStateChange: handle_view_state_change,
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

  function place_draft(side, true_coordinate) {
    state.draft[side] = {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: true_coordinate },
      properties: {
        label: String(state.active_label ?? state.next_label),
        draft: true,
      },
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
    const label = String(state.active_label ?? state.next_label);
    SIDES.forEach((side) => {
      state.features[side].push({
        type: 'Feature',
        geometry: state.draft[side].geometry,
        properties: { label, draft: false },
      });
      state.draft[side] = null;
    });
    if (state.active_label == null) {
      state.next_label += 1;
    }
    state.active_label = null;
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
  // `info.coordinate` is in display (post-rotation) space — every place a
  // picked/dragged point gets written into draft/feature geometry, it must
  // first go through `rotate_point_inverse` to land back in the slice's
  // true data-space coordinates (same contract as `calc_viewport.js`).

  const to_true_coordinate = (side, coordinate) => {
    const [x, y] = rotate_point_inverse(
      coordinate[0],
      coordinate[1],
      state.rotation_state[side]
    );
    return [x, y];
  };

  const set_active_side = (side) => {
    if (state.active_side === side) return;
    state.active_side = side;
    SIDES.forEach((s) => {
      if (panels_wrap[s]) {
        panels_wrap[s].style.borderColor =
          s === side ? '#4f80ff' : 'transparent';
      }
    });
  };

  let dragging = null; // { side, label, is_draft }

  const handle_click = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side) return;
    set_active_side(side);

    if (info.object && info.layer?.id?.startsWith('landmark-icon-')) {
      select_landmark(info.object.properties.label);
      return;
    }

    if (state.selected_label) {
      clear_selection();
      return;
    }

    if (state.mark_mode && !state.draft[side] && info.coordinate) {
      place_draft(side, to_true_coordinate(side, info.coordinate));
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
    const coordinates = to_true_coordinate(side, info.coordinate);
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

  // --- Per-side controls: dropdown, rotation, CELL/TRX, gene search, size ----

  const slice_ids = model.get('slice_ids') || [];
  const slice_labels = model.get('slice_labels') || {};

  const rotation_sliders = {};
  const cell_bar_containers = {};
  const cell_bar_svgs = {};
  const gene_searches = {};

  const rebuild_cell_bar = (side) => {
    const bar_data = cluster_bar_data(state.rows[side]);
    const svg_bar = cell_bar_svgs[side];
    svg_bar.selectAll('*').remove();
    if (!bar_data.length) return;
    const color_dict = Object.fromEntries(
      bar_data.map((d) => [d.name, hexToRgb(d.color)])
    );
    make_bar_graph(
      cell_bar_containers[side],
      (_event, d) => {
        state.highlight_cluster[side] =
          state.highlight_cluster[side] === d.name ? null : d.name;
        rebuild_cell_bar(side);
        refresh();
      },
      svg_bar,
      bar_data,
      color_dict,
      null,
      null,
      null
    );
    svg_bar
      .selectAll('g')
      .style('opacity', (d) =>
        !state.highlight_cluster[side] ||
        d.name === state.highlight_cluster[side]
          ? 1
          : 0.3
      );
  };

  const make_side_column = (side) => {
    const column = document.createElement('div');
    column.style.width = `${column_width}px`;
    column.addEventListener('click', () => set_active_side(side));

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.gap = '6px';
    header.style.marginBottom = '4px';

    const dropdown = make_landmark_dropdown(
      slice_ids,
      slice_labels,
      model.get(`slice_id_${side}`),
      (value) => {
        model.set(`slice_id_${side}`, value);
        model.save_changes();
      }
    );

    const rotation_slider = make_rotation_slider((degrees) => {
      state.rotation_deg_by_slice[model.get(`slice_id_${side}`)] = degrees;
      recompute_rotation_state(side);
      refresh();
    });
    rotation_sliders[side] = rotation_slider;

    header.append(dropdown, rotation_slider.container);

    const controls_top = document.createElement('div');
    controls_top.style.display = 'flex';
    controls_top.style.alignItems = 'center';
    controls_top.style.gap = '8px';
    controls_top.style.marginBottom = '2px';

    const cell_toggle = make_toggle_button('CELL', { checked: true });
    cell_toggle.input.addEventListener('change', () => {
      state.cell_visible[side] = cell_toggle.input.checked;
      refresh();
    });

    const size_slider = make_range_slider(
      {
        min: 1,
        max: 10,
        step: 1,
        value: state.cell_radius[side],
        format: (v) => `${v}px`,
      },
      (value) => {
        state.cell_radius[side] = value;
        refresh();
      }
    );

    // No transcript data is loaded for Landmark (no base_url/tiles) — kept
    // visible-but-disabled for layout parity with Landscape's control bar.
    const trx_toggle = make_toggle_button('TRX', {
      checked: false,
      disabled: true,
    });

    const gene_search = make_gene_search_input((gene) => {
      model.set(`gene_query_${side}`, gene);
      model.save_changes();
    });
    gene_search.set_genes(model.get(`available_genes_${side}`) || []);
    gene_searches[side] = gene_search;

    controls_top.append(
      cell_toggle.container,
      size_slider.container,
      trx_toggle.container,
      gene_search.container
    );

    const bars_row = document.createElement('div');
    bars_row.style.display = 'flex';

    const cell_bar_container = make_bar_container();
    cell_bar_containers[side] = cell_bar_container;
    cell_bar_svgs[side] = d3.create('svg');

    const trx_bar_container = make_bar_container();
    trx_bar_container.style.width = '107px';
    trx_bar_container.style.height = '72px';
    trx_bar_container.style.marginLeft = '5px';
    trx_bar_container.style.border = '1px solid #e8e8e8';
    trx_bar_container.style.color = '#b0b0b0';
    trx_bar_container.style.fontSize = '9px';
    trx_bar_container.style.padding = '4px';
    trx_bar_container.textContent = 'no transcript data';

    bars_row.append(cell_bar_container, trx_bar_container);

    column.append(header, controls_top, bars_row);
    return column;
  };

  const column_a = make_side_column('a');
  const column_b = make_side_column('b');
  columns_row.append(column_a, column_b);

  rebuild_cell_bar('a');
  rebuild_cell_bar('b');

  // One shared canvas renders both views (deck.gl positions them internally
  // via each view's own `x`/`width`) — a per-side "active" border is drawn
  // as a non-interactive overlay rather than splitting the canvas itself.
  const panels_shell = document.createElement('div');
  panels_shell.style.position = 'relative';
  panels_shell.style.width = `${width}px`;
  panels_shell.style.height = `${height}px`;
  panels_shell.style.border = '1px solid #d3d3d3';
  panels_shell.appendChild(panels_row);

  const make_side_overlay = (side, x) => {
    const overlay = document.createElement('div');
    overlay.style.position = 'absolute';
    overlay.style.top = '0';
    overlay.style.left = `${x}px`;
    overlay.style.width = `${panel_width}px`;
    overlay.style.height = `${height}px`;
    overlay.style.boxSizing = 'border-box';
    overlay.style.border = `2px solid ${side === state.active_side ? '#4f80ff' : 'transparent'}`;
    overlay.style.pointerEvents = 'none';
    panels_wrap[side] = overlay;
    return overlay;
  };
  panels_shell.appendChild(make_side_overlay('a', 0));
  panels_shell.appendChild(make_side_overlay('b', panel_width + 4));

  scale_bars.b.container.style.left = `${panel_width + 4 + 10}px`;
  panels_shell.appendChild(scale_bars.a.container);
  panels_shell.appendChild(scale_bars.b.container);

  // --- Shared SLICE / LNDMRK bar graphs ---------------------------------------

  const slice_bar_container = make_bar_container();
  const slice_bar_svg = d3.create('svg');
  const slice_cell_counts = model.get('slice_cell_counts') || {};
  const slice_bar_data = Object.entries(slice_cell_counts)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([name, value]) => ({ name, value }));
  if (slice_bar_data.length) {
    make_bar_graph(
      slice_bar_container,
      (_event, d) => {
        model.set(`slice_id_${state.active_side}`, d.name);
        model.save_changes();
      },
      slice_bar_svg,
      slice_bar_data,
      Object.fromEntries(slice_bar_data.map((d) => [d.name, GRAY_RGB])),
      null,
      null,
      null
    );
  }

  const lndmrk_bar_container = make_bar_container();
  const lndmrk_bar_svg = d3.create('svg');

  const rebuild_lndmrk_bar = () => {
    const coverage = model.get('landmark_coverage') || {};
    const bar_data = Object.entries(coverage).map(([name, value]) => ({
      name,
      value,
    }));
    lndmrk_bar_svg.selectAll('*').remove();
    if (!bar_data.length) return;
    const color_dict = Object.fromEntries(
      bar_data.map((d) => [
        d.name,
        d.name === state.active_label ? ACTIVE_RGB : GRAY_RGB,
      ])
    );
    make_bar_graph(
      lndmrk_bar_container,
      (_event, d) => {
        state.active_label = state.active_label === d.name ? null : d.name;
        rebuild_lndmrk_bar();
      },
      lndmrk_bar_svg,
      bar_data,
      color_dict,
      null,
      null,
      null
    );
  };
  rebuild_lndmrk_bar();
  model.on('change:landmark_coverage', rebuild_lndmrk_bar);

  const slice_label_tag = document.createElement('span');
  slice_label_tag.textContent = 'SLICE';
  slice_label_tag.style.fontSize = '11px';
  slice_label_tag.style.fontWeight = '700';
  slice_label_tag.style.color = 'blue';

  const lndmrk_label_tag = document.createElement('span');
  lndmrk_label_tag.textContent = 'LNDMRK';
  lndmrk_label_tag.style.fontSize = '11px';
  lndmrk_label_tag.style.fontWeight = '700';
  lndmrk_label_tag.style.color = 'blue';

  shared_toolbar_row.append(
    toolbar.container,
    slice_label_tag,
    slice_bar_container,
    lndmrk_label_tag,
    lndmrk_bar_container
  );

  root_container.append(shared_toolbar_row, columns_row, panels_shell);

  // --- React to Python-driven slice swaps ---------------------------------------

  const on_side_swapped = async (side) => {
    state.rows[side] = await decode_centroids(model, side);
    recompute_rotation_state(side);
    set_rotation_slider_value(
      rotation_sliders[side],
      rotation_deg_for_side(side)
    );
    state.features[side] = geojson_to_features(
      model.get(`landmark_geojson_${side}`)
    );
    state.draft[side] = null;
    state.highlight_cluster[side] = null;
    state.gene_active[side] = false;
    state.gene_exp[side] = new Map();
    gene_searches[side].clear();
    gene_searches[side].set_genes(model.get(`available_genes_${side}`) || []);
    rebuild_cell_bar(side);

    const view_id = view_id_for_side(side);
    const new_view_state = initial_view_state_for_centroids(
      state.rows[side],
      panel_width,
      height
    );
    state.view_states = { ...state.view_states, [view_id]: new_view_state };
    sync_zoom_from(view_id, new_view_state.zoom);
    scale_bars[side].update({ zoom: new_view_state.zoom });
    scale_bars[side === 'a' ? 'b' : 'a'].update({
      zoom: state.view_states[other_view_id(view_id)].zoom,
    });
    deck_ist.setProps({ viewState: state.view_states, layers: build_layers() });
  };

  const on_gene_expression_changed = async (side) => {
    const map = await decode_gene_expression(model, side);
    state.gene_exp[side] = map;
    state.gene_active[side] = map.size > 0;
    refresh();
  };

  model.on('change:slice_id_a', () => on_side_swapped('a'));
  model.on('change:slice_id_b', () => on_side_swapped('b'));
  model.on('change:gene_exp_parquet_a', () => on_gene_expression_changed('a'));
  model.on('change:gene_exp_parquet_b', () => on_gene_expression_changed('b'));

  return {
    finalize: () => {
      cleanup_shortcuts();
      deck_ist.finalize();
    },
  };
};
