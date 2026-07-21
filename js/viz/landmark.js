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
  resolve_landmark_color,
} from '../deck-gl/layers/landmark_marker_layer';
import { objects_from_parquet } from '../read_parquet/objects_from_parquet';
import { make_bar_container, make_bar_graph } from '../ui/bar_plot';
import {
  make_landmark_dropdown,
  set_landmark_dropdown_value,
  set_landmark_dropdown_disabled_option,
} from '../ui/landmark_dropdown';
import {
  make_landmark_toolbar,
  set_toolbar_mode,
  set_save_button_active,
  set_del_button_visible,
  register_landmark_keyboard_shortcuts,
  make_rotation_slider,
  set_rotation_slider_value,
  make_toggle_button,
  set_toggle_active,
  make_range_slider,
  make_label_input,
  set_label_input_value,
  set_label_input_visible,
  make_landmark_color_input,
  set_color_input_value,
  set_color_input_visible,
} from '../ui/landmark_ui';
import { hexToRgb, rgbToHex } from '../utils/hexToRgb';
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
    // `enter_mark`/`enter_modify` — all state transitions go through those
    // three, so button visuals and the label textbox never drift out of sync
    // with what's actually happening.
    ui_mode: 'browse',
    // Unsaved MARK points, keyed by *slice id* (not view side) so a
    // landmark can be marked across many slices -- swapping either view to
    // a different slice in between -- and committed all at once on SAVE,
    // rather than being wiped by every slice swap. True (data-space)
    // coordinates, same as `state.features`.
    pending_points: new Map(),
    // The label textbox's value: null in browse; in 'mark' it's the target
    // name (null = not-yet-saved auto-numbered new landmark); in 'modify'
    // it's always the landmark currently targeted.
    active_label: null,
    // In 'mark', the existing label a bar-click targeted (null if this mark
    // was started fresh from the MARK button, with nothing existing yet).
    mark_target_label: null,
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
    cell_opacity: 0.86,
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

  // deck.gl's camera-pan controller and the custom onDrag handler below both
  // respond to the same pointer gesture, so a marker drag also pans the view
  // underneath it. Reactively toggling dragPan *during* a drag loses a race
  // with the controller, so instead pan is turned off for whole *modes*:
  // MODIFY (dragging existing landmarks is the entire point of that mode) is
  // pan-free start to finish, and a MARK draft-drag disables just its side.
  const apply_views = (disabled_sides = []) => {
    set_views_prop(
      deck_ist,
      create_landmark_views(width, height, disabled_sides)
    );
  };

  let dragging = null; // { side, label, is_draft }

  // Recreating the views (to toggle dragPan) *during* a drag cancels the
  // in-progress gesture — that's why marker dragging wasn't working. So the
  // controllers are only ever set at discrete, non-drag moments (mode
  // changes, placing a draft, swapping a slice), never inside a drag handler.
  // MODIFY: pan off on both views for the whole mode. MARK: pan off only on a
  // side already showing a pending point, so a just-placed draft can be
  // dragged to refine it without the camera panning too.
  function refresh_view_controllers() {
    if (state.ui_mode === 'modify') {
      apply_views(['a', 'b']);
      return;
    }
    if (state.ui_mode === 'mark') {
      apply_views(
        SIDES.filter((side) =>
          state.pending_points.has(model.get(`slice_id_${side}`))
        )
      );
      return;
    }
    apply_views([]);
  }
  apply_views([]);

  // A draft's displayed label always reflects the *current* textbox value
  // (not whatever it was when the point was placed), so editing the name
  // live-updates the preview before SAVE.
  const combined_features = (side) => {
    const committed = state.features[side].filter((f) => !f.properties.draft);
    const pending = state.pending_points.get(model.get(`slice_id_${side}`));
    if (!pending) return committed;
    const draft_label = String(state.active_label ?? state.next_label);
    return [
      ...committed,
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: pending },
        properties: { label: draft_label, draft: true },
      },
    ];
  };

  const build_layers = () =>
    SIDES.flatMap((side) => [
      ini_landmark_cell_layer(side, state.rows[side], {
        highlight_cluster: state.highlight_cluster,
        rotation_state: state.rotation_state[side],
        visible: state.cell_visible,
        radius: model.get('cell_radius'),
        opacity: state.cell_opacity,
        highlighted_cell: state.highlighted_cell[side],
      }),
      ini_landmark_marker_layer(side, combined_features(side), {
        rotation_state: state.rotation_state[side],
        visible: state.marker_visible,
        modify_target: state.ui_mode === 'modify' ? state.active_label : null,
        focus_label: current_target_label(),
        color_overrides: model.get('landmark_colors') || {},
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
      const original = state.mark_target_label;
      if (original && value && value !== original) {
        // Renaming an existing landmark right from MARK's textbox — no
        // instance needs to be visible/draggable (i.e. no need to go
        // through MODIFY) just to rename it.
        model.set('rename_landmark', {});
        model.set('rename_landmark', { old: original, new: value });
        model.save_changes();
        state.mark_target_label = value;
        state.active_label = value;
      } else {
        state.active_label =
          value && value !== String(state.next_label) ? value : null;
      }
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

  // The landmark currently targeted/focused — null in 'browse'. Used by the
  // color swatch, the rename logic below, `build_layers`' marker dimming,
  // and the LNDMRK bar's dimming.
  function current_target_label() {
    if (state.ui_mode === 'mark')
      return String(state.active_label ?? state.next_label);
    if (state.ui_mode === 'modify') return state.active_label;
    return null;
  }

  const color_input = make_landmark_color_input((hex) => {
    const label = current_target_label();
    if (!label) return;
    const overrides = { ...(model.get('landmark_colors') || {}) };
    overrides[label] = hex;
    model.set('landmark_colors', overrides);
    model.save_changes();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    refresh();
  });

  function sync_color_input() {
    const label = current_target_label();
    if (!label) return; // hidden anyway
    const overrides = model.get('landmark_colors') || {};
    const hex =
      overrides[String(label)] ||
      rgbToHex(resolve_landmark_color(label, overrides));
    set_color_input_value(color_input, hex);
  }

  // Declared here (before the state machine below, not down with the rest
  // of the control panel) so `enter_mark` can reactivate it directly —
  // clicking MARK should make sure landmarks are actually visible, since
  // marking against a hidden layer doesn't make much sense.
  const lndmrk_toggle = make_toggle_button('LNDMRK', {
    active: state.marker_visible,
    on_toggle: (active) => {
      state.marker_visible = active;
      refresh();
      rebuild_lndmrk_bar();
    },
  });

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
    // MARK (browse's primary button) starts a fresh landmark; while marking
    // it reads CANCEL and returns to browse.
    on_mark_toggle: () => {
      if (state.ui_mode === 'browse') enter_mark(null);
      else enter_browse();
    },
    // MODIFY only shows once a landmark is selected: from MARK (a targeted
    // existing landmark) it jumps into drag/edit mode for it; in modify it
    // reads CANCEL and returns to browse.
    on_modify_toggle: () => {
      if (state.ui_mode === 'modify') enter_browse();
      else if (state.ui_mode === 'mark') enter_modify(state.mark_target_label);
    },
    on_save: () => {
      if (state.ui_mode === 'mark') save_mark();
      else if (state.ui_mode === 'modify') save_modify();
    },
    on_delete: () => {
      if (state.ui_mode === 'modify') delete_modify();
    },
  });

  // In 'mark', SAVE only has something to commit once at least one draft is
  // drawn; in 'modify', it commits a staged rename (or is a no-op exit) once
  // a landmark is targeted.
  const is_save_active = () => {
    if (state.ui_mode === 'mark') return state.pending_points.size > 0;
    if (state.ui_mode === 'modify') return state.active_label != null;
    return false;
  };

  function apply_ui_mode() {
    set_toolbar_mode(toolbar.buttons, state.ui_mode, {
      mark_has_target:
        state.ui_mode === 'mark' && state.mark_target_label != null,
    });
    set_save_button_active(toolbar.buttons, is_save_active());
    set_del_button_visible(
      toolbar.buttons,
      state.ui_mode === 'modify' && state.active_label != null
    );
    set_label_input_visible(label_input, state.ui_mode !== 'browse');
    set_color_input_visible(
      color_input,
      state.ui_mode !== 'browse' && current_target_label() != null
    );
  }

  // Make sure landmarks are actually visible when entering an edit mode —
  // marking/modifying against a hidden LNDMRK layer makes no sense.
  function ensure_landmarks_visible() {
    if (state.marker_visible) return;
    state.marker_visible = true;
    set_toggle_active(lndmrk_toggle, true);
  }

  function enter_browse() {
    state.ui_mode = 'browse';
    state.active_label = null;
    state.mark_target_label = null;
    state.pending_rename = null;
    state.pending_points = new Map();
    sync_label_input();
    sync_color_input();
    apply_ui_mode();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    refresh_view_controllers();
    refresh();
  }

  function enter_mark(label) {
    state.ui_mode = 'mark';
    state.active_label = label;
    // The label a bar-click targeted (vs. null for a fresh MARK-button
    // click) — kept around so the textbox can tell "rename this existing
    // landmark" apart from "name the new one about to be created."
    state.mark_target_label = label;
    state.pending_rename = null;
    state.pending_points = new Map();
    ensure_landmarks_visible();
    sync_label_input();
    sync_color_input();
    apply_ui_mode();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    refresh_view_controllers();
    refresh();
  }

  // Enter (or retarget within) MODIFY. `label` is the landmark to edit, or
  // null to enter the mode with nothing targeted yet (via the MODIFY button —
  // then click a landmark to target it). Pan is turned off for the whole
  // mode by `refresh_view_controllers`, so dragging a landmark can't fight
  // the camera.
  function enter_modify(label) {
    const was_modify = state.ui_mode === 'modify';
    if (was_modify && state.active_label === label) return;
    state.ui_mode = 'modify';
    state.active_label = label;
    state.pending_rename = null;
    state.pending_points = new Map();
    ensure_landmarks_visible();
    sync_label_input();
    sync_color_input();
    apply_ui_mode();
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    if (!was_modify) refresh_view_controllers();
    refresh();
  }

  function place_draft(side, true_coordinate) {
    if (state.ui_mode !== 'mark') return;
    state.pending_points.set(model.get(`slice_id_${side}`), true_coordinate);
    set_save_button_active(toolbar.buttons, is_save_active());
    rebuild_slice_bar();
    // This side now has a draft — turn its pan off so the draft can be
    // dragged to refine it (done here, not mid-drag, to avoid the race).
    refresh_view_controllers();
    refresh();
  }

  function save_mark() {
    if (state.pending_points.size === 0) return;
    const label = String(state.active_label ?? state.next_label);
    const is_new_label = state.active_label == null;

    // Optimistically promote any pending point whose slice happens to be
    // showing on a side right now, from draft to committed, so the view
    // doesn't wait on the round trip to stop looking like a draft. Python
    // will independently confirm this (and every other slice's point, shown
    // or not) via `add_landmark_points` -> `landmark_geojson_*`.
    SIDES.forEach((side) => {
      const slice_id = model.get(`slice_id_${side}`);
      const coordinates = state.pending_points.get(slice_id);
      if (!coordinates) return;
      state.features[side].push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates },
        properties: { label, draft: false },
      });
    });

    const points = Array.from(state.pending_points.entries()).map(
      ([slice_id, coordinates]) => ({
        slice_id,
        x: coordinates[0],
        y: coordinates[1],
      })
    );
    if (is_new_label) state.next_label += 1;
    state.pending_points = new Map();

    model.set('add_landmark_points', {});
    model.set('add_landmark_points', { label, points });
    model.save_changes();

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
  sync_color_input();
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

  // Tracks which side the pointer is over, for the mark-mode cursor only.
  let hover_side = null;

  // A slice can only hold one instance of a given landmark — once this
  // side's current slice already has a pending or committed instance of
  // the label being marked, there's nowhere left to place another one here.
  const is_placement_blocked = (side) => {
    if (state.ui_mode !== 'mark') return true;
    if (state.pending_points.has(model.get(`slice_id_${side}`))) return true;
    const label = String(state.active_label ?? state.next_label);
    return state.features[side].some(
      (f) => !f.properties.draft && f.properties.label === label
    );
  };

  const handle_click = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side) return;
    set_active_side(side);

    const clicked_marker =
      info.object && info.layer?.id?.startsWith('landmark-icon-')
        ? info.object
        : null;
    if (clicked_marker) {
      if (clicked_marker.properties.draft) return; // reposition via drag, not click
      const { label } = clicked_marker.properties;
      if (state.ui_mode === 'modify' && state.active_label === label) {
        // Clicking the already-targeted landmark again clears the target
        // (stays in modify, ready to pick another) rather than exiting.
        enter_modify(null);
      } else {
        // A pure click (no drag) enters/retargets modify safely — the drag
        // race only bites a click-drag gesture, which `can_drag_marker` blocks
        // outside modify.
        enter_modify(label);
      }
      return;
    }

    if (
      state.ui_mode === 'mark' &&
      !is_placement_blocked(side) &&
      info.coordinate
    ) {
      place_draft(side, to_true_coordinate(side, info.coordinate));
      return;
    }

    if (info.object && info.layer?.id?.startsWith('landmark-cell-')) {
      toggle_highlighted_cell(side, info.object.cell_id);
    }
  };

  // Whether a marker can be dragged right now. A committed marker is draggable
  // only *in* modify mode (where pan is already off, so no camera fight) —
  // you enter modify first, by button or by clicking the marker, then drag. A
  // draft marker is draggable while marking, to refine its position.
  const can_drag_marker = (info) => {
    if (!info.object || !info.layer?.id?.startsWith('landmark-icon-')) {
      return false;
    }
    if (info.object.properties.draft) return state.ui_mode === 'mark';
    return state.ui_mode === 'modify';
  };

  const handle_drag_start = (info) => {
    const side = info.viewport && side_for_viewport_id(info.viewport.id);
    if (!side || !can_drag_marker(info)) return;
    const { label, draft: is_draft } = info.object.properties;
    // Retarget within modify (a different committed marker) if needed. Pan is
    // already off for the whole mode, so this doesn't re-init the views
    // mid-gesture — critically, no `apply_views`/`refresh_view_controllers`
    // is called from any drag handler, which is what was cancelling drags.
    if (!is_draft && state.active_label !== label) {
      state.active_label = label;
      state.pending_rename = null;
      sync_label_input();
      sync_color_input();
      apply_ui_mode();
      rebuild_lndmrk_bar();
      rebuild_slice_bar();
    }
    dragging = { side, label, is_draft };
  };

  const handle_drag = (info) => {
    if (!dragging || !info.coordinate) return;
    const { side, label, is_draft } = dragging;
    const coordinates = to_true_coordinate(side, info.coordinate);
    if (is_draft) {
      state.pending_points.set(model.get(`slice_id_${side}`), coordinates);
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
    onHover: (info) => {
      hover_side = info.viewport
        ? side_for_viewport_id(info.viewport.id)
        : null;
    },
    getCursor: ({ isDragging }) => {
      if (isDragging) return 'grabbing';
      if (state.ui_mode === 'modify') return 'move';
      if (state.ui_mode !== 'mark') return 'grab';
      // No crosshair once this side can't take another instance of the
      // targeted landmark — a slice only ever holds one.
      if (hover_side && is_placement_blocked(hover_side)) return 'not-allowed';
      return 'crosshair';
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
      if (state.ui_mode === 'browse') {
        enter_mark(null);
      } else {
        enter_browse();
      }
    },
    on_save: () => {
      if (state.ui_mode === 'mark') save_mark();
      else if (state.ui_mode === 'modify') save_modify();
    },
    on_cancel: () => {
      // Escape is a finer-grained undo than CANCEL: clear every pending
      // (unsaved, across however many slices) point first, staying in
      // 'mark', before falling back to a full exit.
      if (state.ui_mode === 'mark' && state.pending_points.size > 0) {
        state.pending_points = new Map();
        set_save_button_active(toolbar.buttons, is_save_active());
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

  const other_side = (side) => (side === 'a' ? 'b' : 'a');

  // The two views only ever show different slices — if the requested slice
  // is already on the other side, swap instead of leaving both sides on the
  // same (useless-to-align) slice.
  const request_slice_change = (side, new_slice_id) => {
    const opposite = other_side(side);
    if (new_slice_id === model.get(`slice_id_${opposite}`)) {
      model.set(`slice_id_${opposite}`, model.get(`slice_id_${side}`));
    }
    model.set(`slice_id_${side}`, new_slice_id);
    model.save_changes();
  };

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
      (value) => request_slice_change(side, value)
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
  set_landmark_dropdown_disabled_option(dropdowns.a, model.get('slice_id_b'));
  set_landmark_dropdown_disabled_option(dropdowns.b, model.get('slice_id_a'));

  // --- Shared control panel: LNDMRK / CELL / TRX / SLICE ----------------------
  // (`lndmrk_toggle` itself is declared earlier, before the state machine.)

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
    const color_overrides = model.get('landmark_colors') || {};
    const color_dict = Object.fromEntries(
      bar_data.map((d) => [
        d.name,
        resolve_landmark_color(d.name, color_overrides),
      ])
    );
    make_bar_graph(
      lndmrk_bar_container,
      (event, d) => {
        // Shift-click: delete the landmark entirely (every slice it's in).
        // Plain click: target it in MARK, ready to add another instance (or
        // rename it via the textbox — no instance needs to be on-screen for
        // that, so there's no separate shortcut into MODIFY from here).
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
    // A dimmed bar is a display of state too: hidden layer -> every bar
    // dims uniformly; otherwise, whichever landmark is currently targeted
    // (in mark or modify) stays full-opacity and every other one dims, the
    // same visual cue clicking a bar gives on the map itself.
    const target = current_target_label();
    lndmrk_bar_svg.selectAll('g').style('opacity', (d) => {
      if (!state.marker_visible) return 0.2;
      if (!target) return 1;
      return d.name === target ? 1 : 0.4;
    });
  }
  rebuild_lndmrk_bar();
  model.on('change:landmark_coverage', rebuild_lndmrk_bar);

  const cell_toggle = make_toggle_button('CELL', {
    active: state.cell_visible,
    on_toggle: (active) => {
      state.cell_visible = active;
      refresh();
      rebuild_cell_bar();
    },
  });

  // Radius is a fixed widget-construction setting (`cell_radius`, a synced
  // trait) rather than a runtime control -- it rarely needs mid-session
  // adjustment, unlike opacity (frequently useful to turn down to see
  // landmarks/other cells underneath).
  const opacity_slider = make_range_slider(
    {
      min: 0,
      max: 1,
      step: 0.05,
      value: state.cell_opacity,
      format: (v) => v.toFixed(2),
    },
    (value) => {
      state.cell_opacity = value;
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

  function rebuild_cell_bar() {
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
    cell_bar_svg.selectAll('g').style('opacity', (d) => {
      if (!state.cell_visible) return 0.2;
      return !state.highlight_cluster || d.name === state.highlight_cluster
        ? 1
        : 0.3;
    });
  }
  rebuild_cell_bar(); // cluster_counts/cluster_colors are static — no need to rebuild on slice swap

  // No transcript data is loaded for Landmark (no base_url/tiles) — kept
  // visible-but-disabled for layout parity with Landscape's control bar.
  const trx_toggle = make_toggle_button('TRX', {
    active: false,
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
  // The static, complete, already-numerically-ordered list of every slice —
  // used only for row order/labels, so a slice with zero landmarks still
  // gets its own (zero-length, but clickable) row.
  const slice_id_order = model.get('slice_ids') || [];

  function rebuild_slice_bar() {
    slice_bar_svg.selectAll('*').remove();
    if (!slice_id_order.length) return;
    const landmark_slices = model.get('landmark_slices') || {};
    // Bar length = how many distinct landmarks have an instance in that
    // slice (the inverse of landmark_slices' label -> slice ids mapping) —
    // not cell count.
    const landmark_count_by_slice = {};
    Object.values(landmark_slices).forEach((slices_for_label) => {
      slices_for_label.forEach((slice_id) => {
        landmark_count_by_slice[slice_id] =
          (landmark_count_by_slice[slice_id] || 0) + 1;
      });
    });
    // Unsaved MARK points count too, so the SLICE bar grows live as you drop
    // a new landmark's points across slices, before SAVE writes them back.
    const target = current_target_label();
    const covered = new Set(target ? landmark_slices[target] || [] : []);
    if (state.ui_mode === 'mark') {
      state.pending_points.forEach((_coord, slice_id) => {
        if (!covered.has(slice_id)) {
          landmark_count_by_slice[slice_id] =
            (landmark_count_by_slice[slice_id] || 0) + 1;
        }
        covered.add(slice_id);
      });
    }
    const slice_bar_data = slice_id_order.map((name) => ({
      name,
      value: landmark_count_by_slice[name] || 0,
    }));
    const color_overrides = model.get('landmark_colors') || {};
    const color_dict = Object.fromEntries(
      slice_bar_data.map((d) => [
        d.name,
        covered.has(d.name) && target
          ? resolve_landmark_color(target, color_overrides)
          : GRAY_RGB,
      ])
    );
    make_bar_graph(
      slice_bar_container,
      (_event, d) => request_slice_change(state.active_side, d.name),
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
  model.on('change:landmark_colors', () => {
    rebuild_lndmrk_bar();
    rebuild_slice_bar();
    sync_color_input();
    refresh();
  });

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
      [lndmrk_toggle, label_input.container, color_input.container],
      lndmrk_bar_container
    ),
    make_section([cell_toggle, opacity_slider.container], cell_bar_container),
    make_section([trx_toggle], trx_bar_container),
    make_section([make_tag('SLICE')], slice_bar_container)
  );

  root_container.append(control_row, panels_shell);

  // --- React to Python-driven slice swaps ---------------------------------------

  // `slice_id_{side}` changing is a *request* — the front-end model updates
  // it optimistically the instant `model.set` runs, well before Python's
  // `_switch_side` observer has actually recomputed and sent back this new
  // slice's `centroids_parquet_{side}`/`landmark_geojson_{side}`. Decoding
  // centroids here (keyed off `change:slice_id_*`) would grab whatever the
  // *previous* slice's bytes still were — the view would silently keep
  // showing the old slice. So this only does the cheap, immediately-correct
  // UI sync; the actual data refresh below is keyed off the data traits
  // themselves, which Python only touches once the new values are ready.
  const on_slice_id_changed = (side) => {
    const new_slice_id = model.get(`slice_id_${side}`);
    set_landmark_dropdown_value(dropdowns[side], new_slice_id);
    set_landmark_dropdown_disabled_option(
      dropdowns[other_side(side)],
      new_slice_id
    );
    state.highlighted_cell[side] = null;
    set_rotation_slider_value(
      rotation_sliders[side],
      rotation_deg_for_side(side)
    );
    // Pending MARK points are kept by slice id, not side, so they're left
    // alone here -- swapping this side to a different slice is exactly how
    // you mark another instance of the same landmark elsewhere.
    set_save_button_active(toolbar.buttons, is_save_active());
    // This side may now show a slice that does/doesn't have a pending point,
    // so its pan-enabled state can change (see `refresh_view_controllers`).
    refresh_view_controllers();
    rebuild_slice_bar();
  };

  const on_centroids_changed = async (side) => {
    state.rows[side] = await decode_centroids(model, side);
    recompute_rotation_state(side);

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

  // Picking up a landmark rename/slice-switch/etc. (Python-driven, not
  // JS-initiated) for whichever side happens to be showing an affected
  // slice. Harmless no-op re-sync when this fires from our *own* SAVE/DEL
  // writes.
  const on_landmark_geojson_changed = (side) => {
    state.features[side] = geojson_to_features(
      model.get(`landmark_geojson_${side}`)
    );
    refresh();
  };

  model.on('change:slice_id_a', () => on_slice_id_changed('a'));
  model.on('change:slice_id_b', () => on_slice_id_changed('b'));
  model.on('change:centroids_parquet_a', () => on_centroids_changed('a'));
  model.on('change:centroids_parquet_b', () => on_centroids_changed('b'));
  model.on('change:landmark_geojson_a', () => on_landmark_geojson_changed('a'));
  model.on('change:landmark_geojson_b', () => on_landmark_geojson_changed('b'));

  return {
    finalize: () => {
      cleanup_shortcuts();
      deck_ist.finalize();
    },
  };
};
