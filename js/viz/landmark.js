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
} from '../deck-gl/layers/landmark_cell_layer';
import {
  ini_landmark_marker_layer,
  features_to_geojson,
  geojson_to_features,
  color_for_label,
} from '../deck-gl/layers/landmark_marker_layer';
import { objects_from_parquet } from '../read_parquet/objects_from_parquet';
import { make_bar_container, make_bar_graph } from '../ui/bar_plot';
import {
  make_landmark_dropdown,
  set_landmark_dropdown_value,
} from '../ui/landmark_dropdown';
import {
  make_landmark_toolbar,
  set_mark_button_mode,
  set_save_button_visible,
  set_del_button_visible,
  register_landmark_keyboard_shortcuts,
  make_rotation_slider,
  set_rotation_slider_value,
  make_toggle_button,
  make_range_slider,
  make_label_input,
  set_label_input_value,
  set_label_input_visible,
} from '../ui/landmark_ui';
import { hexToRgb } from '../utils/hexToRgb';
import { build_rotation_state, rotate_point_inverse } from '../utils/rotation';
import { create_scale_bar } from '../utils/scale_bar';

const SIDES = ['a', 'b'];
const GRAY_RGB = [160, 160, 160];

const decode_centroids = async (model, side) => {
  const bytes = model.get(`centroids_parquet_${side}`);
  if (!bytes || bytes.byteLength === 0) return [];
  const parsed = await objects_from_parquet(bytes, 'cell_id');
  return centroid_rows_from_parquet(parsed);
};

const style_bar_box = (container) => {
  container.style.width = '107px';
  container.style.height = '72px';
  container.style.marginLeft = '5px';
  container.style.overflowY = 'auto';
  container.style.border = '1px solid #d3d3d3';
};

export const landmark = async (model, el) => {
  el.innerHTML = '';

  const width = model.get('width') || el.clientWidth || 900;
  const height = model.get('height') || 600;
  const panel_width = landmark_panel_width(width);

  const root_container = document.createElement('div');
  root_container.className = 'landmark-root';
  el.appendChild(root_container);

  // One row of "sections" (toolbar, LNDMRK, CELL, TRX, SLICE), each its own
  // small column: top controls directly above that section's own bar box —
  // not two long, unaligned rows (wastes horizontal space and separates a
  // toggle/slider from the bar it controls).
  const control_row = document.createElement('div');
  control_row.style.display = 'flex';
  control_row.style.alignItems = 'flex-start';
  control_row.style.gap = '10px';
  control_row.style.width = `${width}px`;
  control_row.style.flexWrap = 'wrap';
  control_row.style.padding = '4px 0';

  const make_section = (top_els, bar_el) => {
    const section = document.createElement('div');
    section.style.display = 'flex';
    section.style.flexDirection = 'column';
    section.style.alignItems = 'flex-start';
    section.style.gap = '2px';

    const top = document.createElement('div');
    top.style.display = 'flex';
    top.style.alignItems = 'center';
    top.style.gap = '4px';
    top.append(...top_els);

    section.appendChild(top);
    if (bar_el) section.appendChild(bar_el);
    return section;
  };

  const state = {
    // 'browse' (initial; nothing editable) | 'mark' (adding new instances) |
    // 'modify' (drag/rename/delete an existing landmark). See `enter_browse`/
    // `enter_mark`/`ensure_modify` — all state transitions go through those
    // three, so button visuals and the label textbox never drift out of sync
    // with what's actually happening.
    ui_mode: 'browse',
    draft: { a: null, b: null },
    // The label textbox's value: null in browse; in 'mark' it's the target
    // name (null = not-yet-saved auto-numbered new landmark); in 'modify'
    // it's always the landmark currently targeted.
    active_label: null,
    // A typed-but-not-yet-committed rename while in 'modify' — applied on
    // SAVE, not on every keystroke (modify's only way out is save/delete).
    pending_rename: null,
    active_side: 'a',
    next_label: model.get('next_landmark_label') || 1,
    rows: { a: [], b: [] },
    features: { a: [], b: [] },
    // Shared across both views — one CELL/LNDMRK control panel, not one per side.
    highlight_cluster: null,
    cell_visible: true,
    cell_radius: 2,
    marker_visible: true,
    // Per-side single-cell pick (a visual anchor while placing a nearby
    // landmark) — independent of cluster highlighting.
    highlighted_cell: { a: null, b: null },
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

  const panels_wrap = { a: null, b: null };

  const panels_row = document.createElement('div');
  panels_row.style.width = `${width}px`;
  panels_row.style.height = `${height}px`;
  const deck_ist = ini_deck(panels_row, width, height);

  // Disabling the *dragged* side's camera-pan controller while a marker is
  // being dragged — otherwise deck.gl's controller and the custom onDrag
  // handler below both respond to the same pointer gesture, and dragging a
  // pentagon also pans the view underneath it.
  const apply_views = (drag_pan_disabled_side) => {
    set_views_prop(
      deck_ist,
      create_landmark_views(width, height, drag_pan_disabled_side)
    );
  };
  apply_views(null);

  // A draft's displayed label always reflects the *current* textbox value
  // (not whatever it was when the point was placed), so editing the name
  // live-updates the preview before SAVE.
  const combined_features = (side) => {
    const committed = state.features[side].filter((f) => !f.properties.draft);
    if (!state.draft[side]) return committed;
    const draft_label = String(state.active_label ?? state.next_label);
    return [
      ...committed,
      {
        ...state.draft[side],
        properties: { ...state.draft[side].properties, label: draft_label },
      },
    ];
  };

  const build_layers = () =>
    SIDES.flatMap((side) => [
      ini_landmark_cell_layer(side, state.rows[side], {
        highlight_cluster: state.highlight_cluster,
        rotation_state: state.rotation_state[side],
        visible: state.cell_visible,
        radius: state.cell_radius,
        highlighted_cell: state.highlighted_cell[side],
      }),
      ini_landmark_marker_layer(side, combined_features(side), {
        rotation_state: state.rotation_state[side],
        visible: state.marker_visible,
        modify_target: state.ui_mode === 'modify' ? state.active_label : null,
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

  // --- browse / mark / modify state machine -----------------------------------

  // The label textbox: hidden in 'browse'; in 'mark' it's the target name
  // (editable, committing a custom name for the pending draft(s)); in
  // 'modify' it's the targeted landmark's name (editing stages a rename,
  // applied on SAVE — not immediately, since modify's only way out is
  // save/delete).
  const label_input = make_label_input((value) => {
    if (state.ui_mode === 'mark') {
      state.active_label =
        value && value !== String(state.next_label) ? value : null;
      rebuild_lndmrk_bar();
      rebuild_slice_bar();
      refresh();
    } else if (state.ui_mode === 'modify') {
      state.pending_rename =
        value && value !== state.active_label ? value : null;
    }
  });
  function sync_label_input() {
    if (state.ui_mode === 'browse') {
      set_label_input_value(label_input, '');
    } else if (state.ui_mode === 'mark') {
      set_label_input_value(
        label_input,
        state.active_label ?? String(state.next_label)
      );
    } else {
      set_label_input_value(
        label_input,
        state.pending_rename ?? state.active_label ?? ''
      );
    }
  }

  const sync_side_to_model = (side) => {
    // Captured *before* the empty-first set below: that intermediate write
    // fires our own `change:landmark_geojson_*` listener synchronously
    // (see `on_landmark_geojson_changed`), which reacts by rebuilding
    // `state.features[side]` from the (momentarily empty) model value. If
    // the real payload were computed *after* that set, it would compute
    // from the just-wiped state and permanently save an empty collection.
    const real_value = features_to_geojson(state.features[side]);
    model.set(`landmark_geojson_${side}`, {
      type: 'FeatureCollection',
      features: [],
    });
    model.set(`landmark_geojson_${side}`, real_value);
    model.save_changes();
  };

  const toolbar = make_landmark_toolbar({
    on_mark_toggle: () => {
      if (state.ui_mode === 'modify') return; // disabled — save/delete only
      if (state.ui_mode === 'mark') {
        enter_browse();
      } else {
        enter_mark(null);
      }
    },
    on_save: () => {
      if (state.ui_mode === 'mark') save_mark();
      else if (state.ui_mode === 'modify') save_modify();
    },
    on_delete: () => {
      if (state.ui_mode === 'modify') delete_modify();
    },
  });

  function apply_ui_mode() {
    set_mark_button_mode(toolbar.buttons, state.ui_mode);
    set_save_button_visible(toolbar.buttons, state.ui_mode !== 'browse');
    set_del_button_visible(toolbar.buttons, state.ui_mode === 'modify');
    set_label_input_visible(label_input, state.ui_mode !== 'browse');
  }

  function enter_browse() {
    state.ui_mode = 'browse';
    state.active_label = null;
    state.pending_rename = null;
    state.draft.a = null;
    state.draft.b = null;
    sync_label_input();
    apply_ui_mode();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    refresh();
  }

  function enter_mark(label) {
    state.ui_mode = 'mark';
    state.active_label = label;
    state.pending_rename = null;
    state.draft.a = null;
    state.draft.b = null;
    sync_label_input();
    apply_ui_mode();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    refresh();
  }

  function ensure_modify(label) {
    if (state.ui_mode === 'modify' && state.active_label === label) return;
    state.ui_mode = 'modify';
    state.active_label = label;
    state.pending_rename = null;
    state.draft.a = null;
    state.draft.b = null;
    sync_label_input();
    apply_ui_mode();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    refresh();
  }

  function place_draft(side, true_coordinate) {
    if (state.ui_mode !== 'mark') return;
    state.draft[side] = {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: true_coordinate },
      properties: { draft: true },
    };
    refresh();
  }

  function save_mark() {
    if (!state.draft.a && !state.draft.b) return;
    const label = String(state.active_label ?? state.next_label);
    const is_new_label = state.active_label == null;
    const saved_sides = [];
    SIDES.forEach((side) => {
      if (!state.draft[side]) return;
      state.features[side].push({
        type: 'Feature',
        geometry: state.draft[side].geometry,
        properties: { label, draft: false },
      });
      state.draft[side] = null;
      saved_sides.push(side);
    });
    if (is_new_label) state.next_label += 1;
    saved_sides.forEach(sync_side_to_model);
    enter_browse();
  }

  function save_modify() {
    if (state.pending_rename) {
      model.set('rename_landmark', {});
      model.set('rename_landmark', {
        old: state.active_label,
        new: state.pending_rename,
      });
      model.save_changes();
    }
    enter_browse();
  }

  function delete_modify() {
    const label = state.active_label;
    if (!label) return;
    const confirmed = window.confirm(
      `Delete landmark "${label}" entirely, across every slice it appears in? This can't be undone.`
    );
    if (!confirmed) return;
    model.set('delete_landmark', '');
    model.set('delete_landmark', label);
    model.save_changes();
    enter_browse();
  }

  sync_label_input();
  apply_ui_mode();

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

  const toggle_highlighted_cell = (side, cell_id) => {
    state.highlighted_cell[side] =
      state.highlighted_cell[side] === cell_id ? null : cell_id;
    refresh();
  };

  let dragging = null; // { side, label, is_draft }

  const handle_click = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side) return;
    set_active_side(side);

    const clicked_pentagon =
      info.object && info.layer?.id?.startsWith('landmark-icon-')
        ? info.object
        : null;
    if (clicked_pentagon) {
      if (clicked_pentagon.properties.draft) return; // reposition via drag, not click
      const { label } = clicked_pentagon.properties;
      if (state.ui_mode === 'modify' && state.active_label === label) {
        enter_browse();
      } else {
        ensure_modify(label);
      }
      return;
    }

    if (state.ui_mode === 'mark' && !state.draft[side] && info.coordinate) {
      place_draft(side, to_true_coordinate(side, info.coordinate));
      return;
    }

    if (info.object && info.layer?.id?.startsWith('landmark-cell-')) {
      toggle_highlighted_cell(side, info.object.cell_id);
    }
  };

  const handle_drag_start = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side || !info.object || !info.layer?.id?.startsWith('landmark-icon-'))
      return;
    const { label, draft: is_draft } = info.object.properties;
    if (!is_draft) {
      ensure_modify(label);
    } else if (state.ui_mode !== 'mark') {
      return;
    }
    dragging = { side, label, is_draft };
    apply_views(side);
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
    apply_views(null);
  };

  deck_ist.setProps({
    onClick: handle_click,
    onDragStart: handle_drag_start,
    onDrag: handle_drag,
    onDragEnd: handle_drag_end,
    getCursor: ({ isDragging }) => {
      if (isDragging) return 'grabbing';
      return state.ui_mode === 'mark' ? 'crosshair' : 'grab';
    },
    // Available in any state — a quick way to check a cell's cluster or a
    // landmark's name without clicking (which would change state).
    getTooltip: ({ object, layer }) => {
      if (!object) return null;
      if (layer?.id?.startsWith('landmark-icon-')) {
        return { html: `landmark: ${object.properties.label}` };
      }
      if (layer?.id?.startsWith('landmark-cell-')) {
        const cluster_line =
          object.cluster != null ? `cluster: ${object.cluster}<br/>` : '';
        return { html: `${cluster_line}cell: ${object.cell_id}` };
      }
      return null;
    },
  });

  const cleanup_shortcuts = register_landmark_keyboard_shortcuts({
    on_mark_toggle: () => {
      if (state.ui_mode === 'modify') return;
      if (state.ui_mode === 'mark') {
        enter_browse();
      } else {
        enter_mark(null);
      }
    },
    on_save: () => {
      if (state.ui_mode === 'mark') save_mark();
      else if (state.ui_mode === 'modify') save_modify();
    },
    on_cancel: () => {
      // Not in the original spec ("only way out of modify is save/delete")
      // — kept as a safety valve so an accidental click doesn't force a
      // destructive choice. Clears an in-progress draft first if there is one.
      if (state.ui_mode === 'mark' && (state.draft.a || state.draft.b)) {
        state.draft.a = null;
        state.draft.b = null;
        refresh();
        return;
      }
      enter_browse();
    },
    on_delete: () => {
      if (state.ui_mode === 'modify') delete_modify();
    },
  });

  // --- One shared canvas + per-side "active" border overlay -------------------

  const slice_ids = model.get('slice_ids') || [];
  const slice_labels = model.get('slice_labels') || {};
  const rotation_sliders = {};
  const dropdowns = {};

  const panels_shell = document.createElement('div');
  panels_shell.style.position = 'relative';
  panels_shell.style.width = `${width}px`;
  panels_shell.style.height = `${height}px`;
  panels_shell.style.border = '1px solid #d3d3d3';
  panels_shell.appendChild(panels_row);

  // Slice dropdown + rotation slider are inset directly on top of each view
  // (like the scale bar) instead of a separate row — saves vertical space
  // since the panel area they'd otherwise sit above already exists.
  const make_inset_controls = (side, x) => {
    const inset = document.createElement('div');
    inset.style.position = 'absolute';
    inset.style.top = '4px';
    inset.style.left = `${x + 4}px`;
    inset.style.display = 'flex';
    inset.style.alignItems = 'center';
    inset.style.gap = '6px';
    inset.style.padding = '2px 6px';
    inset.style.background = 'rgba(255, 255, 255, 0.85)';
    inset.style.borderRadius = '3px';
    inset.addEventListener('click', () => set_active_side(side));

    const dropdown = make_landmark_dropdown(
      slice_ids,
      slice_labels,
      model.get(`slice_id_${side}`),
      (value) => {
        model.set(`slice_id_${side}`, value);
        model.save_changes();
      }
    );
    dropdowns[side] = dropdown;

    const rotation_slider = make_rotation_slider((degrees) => {
      state.rotation_deg_by_slice[model.get(`slice_id_${side}`)] = degrees;
      recompute_rotation_state(side);
      refresh();
    });
    rotation_sliders[side] = rotation_slider;

    inset.append(dropdown, rotation_slider.container);
    return inset;
  };

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

  panels_shell.appendChild(make_inset_controls('a', 0));
  panels_shell.appendChild(make_inset_controls('b', panel_width + 4));

  // --- Shared control panel: LNDMRK / CELL / TRX / SLICE ----------------------

  const lndmrk_toggle = make_toggle_button('LNDMRK', { checked: true });
  lndmrk_toggle.input.addEventListener('change', () => {
    state.marker_visible = lndmrk_toggle.input.checked;
    refresh();
  });

  const lndmrk_bar_container = make_bar_container();
  style_bar_box(lndmrk_bar_container);
  const lndmrk_bar_svg = d3.create('svg');

  function rebuild_lndmrk_bar() {
    const coverage = model.get('landmark_coverage') || {};
    const bar_data = Object.entries(coverage).map(([name, value]) => ({
      name,
      value,
    }));
    lndmrk_bar_svg.selectAll('*').remove();
    if (!bar_data.length) return;
    const color_dict = Object.fromEntries(
      bar_data.map((d) => [d.name, color_for_label(d.name)])
    );
    make_bar_graph(
      lndmrk_bar_container,
      (event, d) => {
        // Shift-click: delete the landmark entirely (every slice it's in).
        // Double-click: jump straight to MODIFY (rename/delete) without
        // needing a visible instance. Plain click: target it in MARK, ready
        // to add another instance.
        if (event.shiftKey) {
          const confirmed = window.confirm(
            `Delete landmark "${d.name}" entirely, across every slice it appears in? This can't be undone.`
          );
          if (!confirmed) return;
          model.set('delete_landmark', '');
          model.set('delete_landmark', d.name);
          model.save_changes();
          enter_browse();
          return;
        }
        if (state.ui_mode === 'mark' && state.active_label === d.name) {
          enter_browse();
        } else {
          enter_mark(d.name);
        }
      },
      lndmrk_bar_svg,
      bar_data,
      color_dict,
      null,
      null,
      null
    );
    lndmrk_bar_svg
      .selectAll('g')
      .on('dblclick', (_event, d) => ensure_modify(d.name));
  }
  rebuild_lndmrk_bar();
  model.on('change:landmark_coverage', rebuild_lndmrk_bar);

  const cell_toggle = make_toggle_button('CELL', { checked: true });
  cell_toggle.input.addEventListener('change', () => {
    state.cell_visible = cell_toggle.input.checked;
    refresh();
  });

  const size_slider = make_range_slider(
    {
      min: 1,
      max: 10,
      step: 1,
      value: state.cell_radius,
      format: (v) => `${v}px`,
    },
    (value) => {
      state.cell_radius = value;
      refresh();
    }
  );

  const cell_bar_container = make_bar_container();
  style_bar_box(cell_bar_container);
  const cell_bar_svg = d3.create('svg');

  const cluster_counts = model.get('cluster_counts') || {};
  const cluster_colors = model.get('cluster_colors') || {};
  const cell_bar_data = Object.entries(cluster_counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  const rebuild_cell_bar = () => {
    cell_bar_svg.selectAll('*').remove();
    if (!cell_bar_data.length) return;
    const color_dict = Object.fromEntries(
      cell_bar_data.map((d) => [
        d.name,
        hexToRgb(cluster_colors[d.name] || '#4f80ff'),
      ])
    );
    make_bar_graph(
      cell_bar_container,
      (_event, d) => {
        state.highlight_cluster =
          state.highlight_cluster === d.name ? null : d.name;
        rebuild_cell_bar();
        refresh();
      },
      cell_bar_svg,
      cell_bar_data,
      color_dict,
      null,
      null,
      null
    );
    cell_bar_svg
      .selectAll('g')
      .style('opacity', (d) =>
        !state.highlight_cluster || d.name === state.highlight_cluster ? 1 : 0.3
      );
  };
  rebuild_cell_bar(); // cluster_counts/cluster_colors are static — no need to rebuild on slice swap

  // No transcript data is loaded for Landmark (no base_url/tiles) — kept
  // visible-but-disabled for layout parity with Landscape's control bar.
  const trx_toggle = make_toggle_button('TRX', {
    checked: false,
    disabled: true,
  });
  const trx_bar_container = make_bar_container();
  style_bar_box(trx_bar_container);
  trx_bar_container.style.border = '1px solid #e8e8e8';
  trx_bar_container.style.color = '#b0b0b0';
  trx_bar_container.style.fontSize = '9px';
  trx_bar_container.style.padding = '4px';
  trx_bar_container.textContent = 'no transcript data';

  const slice_bar_container = make_bar_container();
  style_bar_box(slice_bar_container);
  const slice_bar_svg = d3.create('svg');
  const slice_cell_counts = model.get('slice_cell_counts') || {};
  const slice_bar_data = Object.entries(slice_cell_counts)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([name, value]) => ({ name, value }));

  function rebuild_slice_bar() {
    slice_bar_svg.selectAll('*').remove();
    if (!slice_bar_data.length) return;
    const landmark_slices = model.get('landmark_slices') || {};
    const covered = new Set(
      state.active_label ? landmark_slices[state.active_label] || [] : []
    );
    const color_dict = Object.fromEntries(
      slice_bar_data.map((d) => [
        d.name,
        covered.has(d.name) ? color_for_label(state.active_label) : GRAY_RGB,
      ])
    );
    make_bar_graph(
      slice_bar_container,
      (_event, d) => {
        model.set(`slice_id_${state.active_side}`, d.name);
        model.save_changes();
      },
      slice_bar_svg,
      slice_bar_data,
      color_dict,
      null,
      null,
      null
    );
  }
  rebuild_slice_bar();
  model.on('change:landmark_slices', rebuild_slice_bar);

  const make_tag = (text) => {
    const tag = document.createElement('span');
    tag.textContent = text;
    tag.style.fontSize = '11px';
    tag.style.fontWeight = '700';
    tag.style.color = 'blue';
    return tag;
  };

  control_row.append(
    make_section([toolbar.container], null),
    make_section(
      [lndmrk_toggle.container, label_input.container],
      lndmrk_bar_container
    ),
    make_section(
      [cell_toggle.container, size_slider.container],
      cell_bar_container
    ),
    make_section([trx_toggle.container], trx_bar_container),
    make_section([make_tag('SLICE')], slice_bar_container)
  );

  root_container.append(control_row, panels_shell);

  // --- React to Python-driven slice swaps ---------------------------------------

  const on_side_swapped = async (side) => {
    set_landmark_dropdown_value(dropdowns[side], model.get(`slice_id_${side}`));
    state.highlighted_cell[side] = null;
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

  // Picking up a landmark rename (Python-driven, not JS-initiated) for
  // whichever side happens to be showing an affected slice. Harmless no-op
  // re-sync when this fires from our *own* SAVE/DEL writes.
  const on_landmark_geojson_changed = (side) => {
    state.features[side] = geojson_to_features(
      model.get(`landmark_geojson_${side}`)
    );
    refresh();
  };

  model.on('change:slice_id_a', () => on_side_swapped('a'));
  model.on('change:slice_id_b', () => on_side_swapped('b'));
  model.on('change:landmark_geojson_a', () => on_landmark_geojson_changed('a'));
  model.on('change:landmark_geojson_b', () => on_landmark_geojson_changed('b'));

  return {
    finalize: () => {
      cleanup_shortcuts();
      deck_ist.finalize();
    },
  };
};
