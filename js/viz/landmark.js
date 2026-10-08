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
  ini_landmark_label_layer,
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

  // Take keyboard focus while interacting so the notebook's command-mode
  // shortcuts (m -> markdown, a/b -> insert cell, d d -> delete cell, …) don't
  // fire over the widget, and so the widget's own shortcuts (registered on
  // root_container below) work without an explicit click first.
  root_container.tabIndex = -1;
  root_container.style.outline = 'none';

  // Grab focus as soon as the pointer is over the widget (so "l" etc. work on
  // hover, no click needed) — but never yank focus out of a text field/editor
  // the user is actively typing in, or out of one of the widget's own inputs.
  const focus_root = () => {
    const active = document.activeElement;
    const tag = active?.tagName?.toLowerCase();
    const is_typing =
      active?.isContentEditable || tag === 'input' || tag === 'textarea';
    if (!is_typing && !root_container.contains(active)) {
      root_container.focus({ preventScroll: true });
    }
  };
  root_container.addEventListener('mouseenter', focus_root);
  // Also on click (capture phase, so it wins even if a layer stops the event),
  // skipping form controls which manage their own focus.
  root_container.addEventListener(
    'pointerdown',
    (event) => {
      const tag = event.target?.tagName?.toLowerCase();
      if (['input', 'button', 'select', 'textarea'].includes(tag)) return;
      root_container.focus({ preventScroll: true });
    },
    true
  );

  // Swallow unmodified keydowns so they never reach Jupyter's command-mode
  // handlers. Ctrl/Cmd/Alt combos and Shift+Enter (run cell / save notebook)
  // still pass through. The widget's own shortcut handler is a separate
  // listener on this same element, so it still fires (stopPropagation only
  // stops propagation to *other* elements, not same-element listeners).
  root_container.addEventListener('keydown', (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'Enter' && event.shiftKey) return; // Shift+Enter: run cell
    event.stopPropagation();
  });

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

  const make_section = (top_els, bar_el, { top_width = null } = {}) => {
    const section = document.createElement('div');
    section.style.display = 'flex';
    section.style.flexDirection = 'column';
    section.style.alignItems = 'flex-start';
    section.style.gap = '2px';

    const top = document.createElement('div');
    top.style.display = 'flex';
    top.style.alignItems = 'center';
    top.style.gap = '4px';
    // A fixed-width, wrapping top row keeps the section from changing width
    // as its controls (e.g. the LNDMRK label box + color swatch) show/hide,
    // so the rest of the panel doesn't shift sideways.
    if (top_width != null) {
      top.style.width = `${top_width}px`;
      top.style.flexWrap = 'wrap';
    }
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
    // Shared across both views — one CELL/LNDMRK control panel, not one per
    // side. `highlight_cluster` is kept in sync both ways: clicking a CELL
    // bar or clicking a cell in either scatterplot sets it (like Landscape).
    highlight_cluster: null,
    cell_visible: true,
    cell_opacity: 0.86,
    marker_visible: true,
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
  // Per-view controllers only (set via `create_landmark_views`) — no top-level
  // controller, so the left panel's `dragPan:false` isn't overridden by a
  // default-view controller (which made left-panel marker drags also pan).
  const deck_ist = ini_deck(panels_row, width, height, '', {
    per_view_controllers: true,
  });

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

  // Assigned once the STEP-Z control is built (below); a no-op until then so
  // set_active_side (defined earlier) can refresh the slice indicator's colors.
  let update_step_z_label = () => {};

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
      }),
      ini_landmark_marker_layer(side, combined_features(side), {
        rotation_state: state.rotation_state[side],
        visible: state.marker_visible,
        modify_target: state.ui_mode === 'modify' ? state.active_label : null,
        focus_label: current_target_label(),
        color_overrides: model.get('landmark_colors') || {},
      }),
      ini_landmark_label_layer(side, combined_features(side), {
        rotation_state: state.rotation_state[side],
        visible: state.marker_visible,
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

  // Bounding box of a side's cells, for mapping a zoom focal point onto the
  // equivalent relative spot in the other slice.
  const bbox_of_side = (side) => {
    const rows = state.rows[side];
    if (!rows || !rows.length) return null;
    let minx = Infinity;
    let maxx = -Infinity;
    let miny = Infinity;
    let maxy = -Infinity;
    for (const r of rows) {
      if (r.x < minx) minx = r.x;
      if (r.x > maxx) maxx = r.x;
      if (r.y < miny) miny = r.y;
      if (r.y > maxy) maxy = r.y;
    }
    return { minx, maxx, miny, maxy };
  };

  // Map a focal point (view target) in one side's slice to the same fractional
  // position within the other side's slice, so zooming into e.g. the upper-left
  // of the left panel brings up the upper-left of the right panel's slice
  // rather than its center.
  const map_focal_to_partner = (src_side, target, dst_side) => {
    const src = bbox_of_side(src_side);
    const dst = bbox_of_side(dst_side);
    if (!src || !dst) return null;
    const fx = (target[0] - src.minx) / (src.maxx - src.minx || 1);
    const fy = (target[1] - src.miny) / (src.maxy - src.miny || 1);
    return [
      dst.minx + fx * (dst.maxx - dst.minx),
      dst.miny + fy * (dst.maxy - dst.miny),
      0,
    ];
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
    const prev = state.view_states[viewId] || {};
    const zoom_changed =
      Number.isFinite(prev.zoom) && prev.zoom !== viewState.zoom;
    state.view_states = { ...state.view_states, [viewId]: viewState };

    const side = side_for_viewport_id(viewId);
    const partner_view = other_view_id(viewId);
    const partner_side = side_for_viewport_id(partner_view);

    // Zoom stays locked across both panels. On a zoom (which pulls the target
    // toward the cursor) also move the partner's focal point to the matching
    // relative spot in its own slice; a plain pan is left independent.
    const partner_state = {
      ...state.view_states[partner_view],
      zoom: viewState.zoom,
    };
    if (zoom_changed && side && partner_side) {
      const mapped = map_focal_to_partner(side, viewState.target, partner_side);
      if (mapped) partner_state.target = mapped;
    }
    state.view_states = { ...state.view_states, [partner_view]: partner_state };

    deck_ist.setProps({ viewState: state.view_states });
    if (side) scale_bars[side].update({ zoom: viewState.zoom });
    if (partner_side) {
      scale_bars[partner_side].update({ zoom: viewState.zoom });
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
  // Stage the typed value *locally* (no model write) — updates the preview
  // and, in 'modify', the pending rename. Shared by the live on_input (so
  // SAVE lights up as you type) and on_commit.
  function stage_label(value) {
    if (state.ui_mode === 'mark') {
      const original = state.mark_target_label;
      if (original && value && value !== original) {
        state.pending_rename = value; // renaming an existing targeted landmark
        state.active_label = value;
      } else {
        state.pending_rename = null;
        state.active_label =
          value && value !== String(state.next_label) ? value : null;
      }
    } else if (state.ui_mode === 'modify') {
      state.pending_rename =
        value && value !== state.active_label ? value : null;
    }
  }

  const label_input = make_label_input({
    // Live: reflect the typed value immediately (SAVE turns blue), but don't
    // write a rename through until an explicit commit.
    on_input: (value) => {
      stage_label(value);
      apply_ui_mode();
      refresh();
    },
    on_commit: (value, committed) => {
      stage_label(value);
      if (committed && state.pending_rename) {
        // Enter is an explicit commit — apply the staged rename now.
        const original =
          state.ui_mode === 'mark'
            ? state.mark_target_label
            : state.active_label;
        apply_rename(original, state.pending_rename);
        state.active_label = state.pending_rename;
        if (state.ui_mode === 'mark')
          state.mark_target_label = state.pending_rename;
        state.pending_rename = null;
        sync_label_input();
      }
      // Enter in the name field also saves the landmark, once at least one point
      // is placed — the fluid "type name -> Enter" flow. (An accidental Enter
      // before placing anything just keeps the name and stays in MARK.)
      if (
        committed &&
        state.ui_mode === 'mark' &&
        state.pending_points.size > 0
      ) {
        save_mark();
        return;
      }
      rebuild_lndmrk_bar();
      rebuild_slice_bar();
      apply_ui_mode();
      refresh();
    },
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
    // MARK (browse's primary button) starts a fresh landmark; a toggle, so
    // clicking it again while marking returns to browse.
    on_mark_toggle: () => {
      if (state.ui_mode === 'browse') enter_mark(null);
      else enter_browse();
    },
    // MODIFY only shows once a landmark is selected: from MARK (a targeted
    // existing landmark) it jumps into drag/edit mode for it; in modify it's
    // a toggle back to browse.
    on_modify_toggle: () => {
      if (state.ui_mode === 'modify') enter_browse();
      else if (state.ui_mode === 'mark') enter_modify(state.mark_target_label);
    },
    on_save: () => {
      if (!is_save_active()) return; // gray SAVE is inert (nothing to commit)
      if (state.ui_mode === 'mark') save_mark();
      else if (state.ui_mode === 'modify') save_modify();
    },
    on_delete: () => {
      if (state.ui_mode === 'modify') delete_modify();
    },
  });

  // The landmark-name textbox and color swatch live at the bottom of the
  // toolbar column, below the MARK/MODIFY/SAVE/DEL buttons — they're editing
  // controls for the current landmark, so they belong with the mode buttons
  // rather than over in the LNDMRK bar section.
  toolbar.container.append(label_input.container, color_input.container);

  // SAVE lights up only when it has something to commit: in 'mark', once at
  // least one point is drawn (or a targeted landmark's rename is staged); in
  // 'modify', once a rename is tentatively typed (drags auto-commit, so a
  // rename is the only thing SAVE itself applies).
  function is_save_active() {
    if (state.ui_mode === 'mark') {
      return (
        state.pending_points.size > 0 ||
        (state.mark_target_label != null && state.pending_rename != null)
      );
    }
    if (state.ui_mode === 'modify') return state.pending_rename != null;
    return false;
  }

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

  // The next landmark the *active* slice is missing but its sister panel's
  // slice already has — so MARK can auto-suggest replicating a set across
  // slices (place, save, advance to the next missing one) instead of always
  // naming a brand-new landmark. Null when nothing's missing.
  function next_missing_label() {
    const active = state.active_side;
    const sister = active === 'a' ? 'b' : 'a';
    const current = new Set(
      state.features[active]
        .filter((f) => !f.properties.draft)
        .map((f) => f.properties.label)
    );
    for (const f of state.features[sister]) {
      if (!f.properties.draft && !current.has(f.properties.label)) {
        return f.properties.label;
      }
    }
    return null;
  }

  function enter_mark(label) {
    // A fresh MARK (L / MARK button, label == null) pre-fills the next label the
    // current slice is missing vs its sister panel, as an editable default —
    // mark_target_label stays null, so typing names a *new* landmark rather than
    // renaming the suggested one.
    const suggested = label == null ? next_missing_label() : null;
    state.ui_mode = 'mark';
    state.active_label = label ?? suggested;
    // The label a bar-click targeted (vs. null for a fresh/suggested MARK) —
    // kept around so the textbox can tell "rename this existing landmark" apart
    // from "name the new one about to be created."
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
    // NB: the name field is deliberately NOT focused here — you place the
    // landmark first, then it focuses (see place_draft), which feels more
    // natural than naming before the point exists.
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
    // Always refresh (not just on entry): retargeting to a marker on the other
    // side changes active_side, which is what the modify-mode pan-off follows.
    // A click is a discrete, non-drag moment, so recreating the views is safe.
    refresh_view_controllers();
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
    // Landmark placed — now focus the name field (with the suggested name
    // selected) so you can accept/type a name and press Enter to finish.
    label_input.input.focus();
    label_input.input.select();
  }

  // One-shot whole-landmark rename (every slice it appears in). Fired only
  // from an explicit commit — Enter in the textbox, or SAVE — never on blur.
  function apply_rename(old_label, new_label) {
    if (!old_label || !new_label || old_label === new_label) return;
    model.set('rename_landmark', {});
    model.set('rename_landmark', { old: old_label, new: new_label });
    model.save_changes();
  }

  function save_mark() {
    // Apply a staged rename of the targeted landmark first (if the textbox
    // was edited but not Enter-committed), so its new points land on the new
    // name.
    if (state.mark_target_label && state.pending_rename) {
      apply_rename(state.mark_target_label, state.pending_rename);
      state.active_label = state.pending_rename;
      state.mark_target_label = state.pending_rename;
      state.pending_rename = null;
    }
    if (state.pending_points.size === 0) {
      enter_browse();
      return;
    }
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

    // Advance the queue: if the current slice is still missing landmarks its
    // sister panel has, stay in MARK and suggest the next one (place, save,
    // repeat) — the just-saved point was optimistically promoted above, so it's
    // already excluded. Otherwise return to browse.
    if (next_missing_label() != null) {
      enter_mark(null);
    } else {
      enter_browse();
    }

    // Return focus to the widget so the next landmark flows without a click:
    // saving via Enter blurs the name box (and the mouse is already over the
    // view, so `mouseenter` won't re-fire to re-grab focus). enter_mark above
    // has already refreshed the name box to the next suggestion, so the input's
    // blur -> on_commit(committed=false) that this triggers just re-stages that
    // same value (a harmless no-op).
    root_container.focus({ preventScroll: true });
  }

  function save_modify() {
    if (state.pending_rename)
      apply_rename(state.active_label, state.pending_rename);
    enter_browse();
  }

  function delete_modify() {
    const label = state.active_label;
    if (!label) return;
    // DEL removes this landmark from the CURRENT slice only (the active panel),
    // via the same per-side geojson round-trip a drag uses. Deleting it from
    // *every* slice is the explicit shift-click on the LNDMRK bar. Single-slice
    // delete is low-stakes (just re-mark it), so no confirm prompt.
    const side = state.active_side;
    state.features[side] = state.features[side].filter(
      (f) => f.properties.draft || f.properties.label !== label
    );
    sync_side_to_model(side);
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
    update_step_z_label();
  };

  // Clicking a cell (or a CELL bar) highlights that whole *cluster* and dims
  // the rest — the same on the scatterplot and the bar graph, kept in sync
  // both ways, exactly like Landscape. Whole-cluster (not single-cell) so a
  // highlighted point never reads as a landmark marker.
  function toggle_highlight_cluster(cluster) {
    if (cluster == null) return;
    state.highlight_cluster =
      state.highlight_cluster === cluster ? null : cluster;
    rebuild_cell_bar();
    refresh();
  }

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
      info.object && info.layer?.id?.startsWith('landmark-marker-')
        ? info.object
        : null;
    if (clicked_marker) {
      if (clicked_marker.properties.draft) return; // reposition via drag, not click
      const { label } = clicked_marker.properties;
      // Clicking a landmark toggles editing it: click once to enter modify
      // (drag/rename/delete) for it; click the same one again to exit back
      // to browse (same as the CANCEL button).
      if (state.ui_mode === 'modify' && state.active_label === label) {
        enter_browse();
      } else {
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

    // In browse, clicking a cell highlights its cluster (and the matching
    // CELL bar) — a quick way to inspect where a cluster sits before marking.
    if (
      state.ui_mode === 'browse' &&
      info.object &&
      info.layer?.id?.startsWith('landmark-cell-')
    ) {
      toggle_highlight_cluster(info.object.cluster);
    }
  };

  // Whether a marker can be dragged right now. A committed marker is draggable
  // only *in* modify mode (where pan is already off, so no camera fight) —
  // you enter modify first, by button or by clicking the marker, then drag. A
  // draft marker is draggable while marking, to refine its position.
  const can_drag_marker = (info) => {
    if (!info.object || !info.layer?.id?.startsWith('landmark-marker-')) {
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
      if (layer?.id?.startsWith('landmark-marker-')) {
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

  const cleanup_shortcuts = register_landmark_keyboard_shortcuts(
    {
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
    },
    root_container
  );

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
        // Plain click: toggle targeting it in MARK — ready to add another
        // instance, rename it via the textbox, or jump to drag/edit via the
        // MODIFY button (which appears once a landmark is targeted). Click
        // the same bar again to return to browse.
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
      (_event, d) => toggle_highlight_cluster(d.name),
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

  // A plain, non-interactive section label. Near-black (not blue) on purpose:
  // SLICE isn't clickable, and blue is reserved for things that are (the
  // web-1.0 convention the LNDMRK/CELL toggles and MARK/MODIFY buttons follow).
  const make_tag = (text) => {
    const tag = document.createElement('span');
    tag.textContent = text;
    tag.style.fontSize = '11px';
    tag.style.fontWeight = '700';
    tag.style.color = '#1a1a1a';
    return tag;
  };

  // --- Slice pagination: step BOTH panels one slice in Z at once --------------
  // The big pain in a 10-slice stack is "walking" 1->10: dropdown-picking each
  // panel every step. These step both panels together (preserving their offset)
  // so you can page up/down Z and keep marking.
  const make_step_button = (label, title) => {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.title = title;
    btn.style.cssText =
      'font-size:14px;width:28px;height:24px;padding:0;line-height:1;' +
      'border:1px solid #d3d3d3;border-radius:3px;background:#fff;color:#1e90ff;';
    return btn;
  };
  const prev_slice_button = make_step_button(
    '◀',
    'Both panels one slice back in Z'
  );
  const next_slice_button = make_step_button(
    '▶',
    'Both panels one slice forward in Z'
  );

  const step_slices = (delta) => {
    const ia = slice_ids.indexOf(model.get('slice_id_a'));
    const ib = slice_ids.indexOf(model.get('slice_id_b'));
    if (ia < 0 || ib < 0) return;
    const na = ia + delta;
    const nb = ib + delta;
    // Keep the whole window in range so both panels always show a real slice.
    if (na < 0 || nb < 0 || na >= slice_ids.length || nb >= slice_ids.length) {
      return;
    }
    model.set('slice_id_a', slice_ids[na]);
    model.set('slice_id_b', slice_ids[nb]);
    model.save_changes();
  };

  const update_pagination_enabled = () => {
    const ia = slice_ids.indexOf(model.get('slice_id_a'));
    const ib = slice_ids.indexOf(model.get('slice_id_b'));
    const at_start = Math.min(ia, ib) <= 0;
    const at_end = Math.max(ia, ib) >= slice_ids.length - 1;
    prev_slice_button.disabled = at_start;
    next_slice_button.disabled = at_end;
    prev_slice_button.style.opacity = at_start ? '0.35' : '1';
    next_slice_button.style.opacity = at_end ? '0.35' : '1';
    prev_slice_button.style.cursor = at_start ? 'default' : 'pointer';
    next_slice_button.style.cursor = at_end ? 'default' : 'pointer';
  };

  prev_slice_button.addEventListener('click', () => step_slices(-1));
  next_slice_button.addEventListener('click', () => step_slices(1));

  // The two currently-shown slice ids (left:right), the focused/active panel's
  // id in purple, the other in gray — so you always know where in Z you are.
  const step_z_label = document.createElement('span');
  step_z_label.style.cssText =
    'font-size:12px;font-weight:700;font-family:monospace;min-width:36px;text-align:center;';
  step_z_label.title = 'left : right slice (focused panel = purple)';
  update_step_z_label = () => {
    const a = model.get('slice_id_a');
    const b = model.get('slice_id_b');
    const la = slice_labels[a] ?? a;
    const lb = slice_labels[b] ?? b;
    const gray = '#9aa0a6';
    const purple = '#8b5cf6';
    const ca = state.active_side === 'a' ? purple : gray;
    const cb = state.active_side === 'b' ? purple : gray;
    step_z_label.innerHTML =
      `<span style="color:${ca}">${la}</span>` +
      `<span style="color:${gray}">:</span>` +
      `<span style="color:${cb}">${lb}</span>`;
  };
  update_step_z_label();

  const pagination_control = document.createElement('div');
  pagination_control.style.cssText = 'display:flex;align-items:center;gap:4px;';
  pagination_control.append(prev_slice_button, step_z_label, next_slice_button);
  update_pagination_enabled();

  control_row.append(
    // The label textbox + color swatch are appended into `toolbar.container`
    // above, so they sit under the buttons here.
    make_section([toolbar.container], null),
    make_section([make_tag('STEP Z'), pagination_control], null),
    make_section([lndmrk_toggle], lndmrk_bar_container),
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
    update_pagination_enabled();
    update_step_z_label();
  };

  const on_centroids_changed = async (side) => {
    const view_id = view_id_for_side(side);
    const prev = state.view_states[view_id];
    const old_bbox = bbox_of_side(side); // pre-swap rows

    state.rows[side] = await decode_centroids(model, side);
    recompute_rotation_state(side);

    const fit = initial_view_state_for_centroids(
      state.rows[side],
      panel_width,
      height
    );
    const new_bbox = bbox_of_side(side);
    // Preserve the user's zoom AND pan offset across a slice swap: keep the same
    // fractional spot within the slice's bounding box, so paginating Z holds the
    // view on the same anatomical region instead of recentering. Fit-to-slice
    // only on a side's very first load.
    const first_load = !prev || !Number.isFinite(prev.zoom);
    let new_view_state;
    if (first_load) {
      new_view_state = fit;
    } else if (old_bbox && new_bbox) {
      const fx =
        (prev.target[0] - old_bbox.minx) / (old_bbox.maxx - old_bbox.minx || 1);
      const fy =
        (prev.target[1] - old_bbox.miny) / (old_bbox.maxy - old_bbox.miny || 1);
      new_view_state = {
        ...prev,
        target: [
          new_bbox.minx + fx * (new_bbox.maxx - new_bbox.minx),
          new_bbox.miny + fy * (new_bbox.maxy - new_bbox.miny),
          0,
        ],
      };
    } else {
      new_view_state = { ...prev, target: fit.target };
    }
    state.view_states = { ...state.view_states, [view_id]: new_view_state };
    if (first_load) sync_zoom_from(view_id, new_view_state.zoom);
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
