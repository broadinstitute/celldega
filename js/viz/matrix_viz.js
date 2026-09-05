// The Celldega Matrix Vizualization Method is being built using the approaches
// and code adaptations from the Clustergrammer-GL library, which is available at
// github.com/ismms-himc/clustergrammer-gl
// and being used under the license
//
// MIT License
//
// Copyright (c) 2021 Nicolas Fernandez
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

import {
  clear_cat_hover,
  ini_row_cat_layer,
  ini_col_cat_layer,
  set_cat_layer_handlers,
} from '../deck-gl/matrix/cat_layers';
import {
  clear_composition_hover,
  ini_composition_layer,
  set_composition_layer_onhover,
} from '../deck-gl/matrix/composition_layer';
import { initialize_matrix_crop } from '../deck-gl/matrix/crop';
import { ini_deck } from '../deck-gl/matrix/deck_mat';
import {
  clear_dendro_hover,
  ini_dendro_layer,
  refresh_composition_dendro,
  refresh_dendro_for_viz_mode,
  set_dendro_layer_onclick,
  set_dendro_layer_onhover,
  toggle_dendro_layer_visibility,
} from '../deck-gl/matrix/dendro_layers';
import {
  ini_row_label_layer,
  ini_row_label_focus_layer,
  ini_col_label_layer,
  refresh_row_label_highlight,
  refresh_row_label_styles,
  set_row_label_layer_onclick,
  set_col_label_layer_onclick,
  set_row_label_layer_onhover,
  set_col_label_layer_onhover,
} from '../deck-gl/matrix/label_layers';
import {
  ini_mat_layer,
  set_mat_layer_onclick,
  set_mat_layer_onhover,
} from '../deck-gl/matrix/mat_layer';
import {
  get_mat_layers_list,
  layer_filter,
  mat_reorder_triggers,
} from '../deck-gl/matrix/matrix_layers';
import { get_tooltip } from '../deck-gl/matrix/matrix_tooltip';
import { on_view_state_change } from '../deck-gl/matrix/on_view_state_change';
import { apply_rank_view } from '../deck-gl/matrix/rank_views';
import { focus_matrix_row } from '../deck-gl/matrix/row_search';
import { ini_views, ini_view_state } from '../deck-gl/matrix/views';
import { ini_zoom_data } from '../deck-gl/matrix/zoom';
import {
  apply_manual_definitions_to_axis,
  refresh_attribute_layers,
} from '../matrix/attr_state';
import {
  refresh_row_label_visibility,
  set_composition_colors,
} from '../matrix/composition_data';
import {
  crop_fade_signature,
  crop_filter_signature,
  filter_matrix_data,
} from '../matrix/crop_filter';
import { calc_dendro_polygons, ini_dendro } from '../matrix/dendro';
import {
  set_row_label_data,
  set_col_label_data,
  update_label_display_names,
} from '../matrix/label_data';
import {
  set_mat_data,
  apply_mat_encoding,
  resolve_viz_mode,
} from '../matrix/mat_data';
import {
  buildCellSlice,
  buildColAxisSlice,
  buildRowAxisSlice,
  buildRowColPairSlice,
} from '../matrix/matrix_axis_slice';
import {
  ini_rank_views,
  resolve_rank_view_level,
  set_rank_view_state,
} from '../matrix/rank_views';
import { set_mat_constants } from '../matrix/set_constants';
import { initialize_attribute_editor } from '../ui/attribute_editor';
import { initialize_attribute_labels } from '../ui/attribute_labels';
import {
  make_matrix_ui_container,
  update_mode_button_visibility,
} from '../ui/ui_containers';

export const matrix_viz = async (
  model,
  el,
  network,
  width = '800',
  height = '800',
  row_label_callback = null,
  col_label_callback = null,
  col_dendro_callback = null
) => {
  const root = document.createElement('div');
  root.style.border = '1px solid #d3d3d3';
  const deck_mat = ini_deck(root, width, height);

  const row_entity = model.get('row_entity');
  const col_entity = model.get('col_entity');

  const viz_state = set_mat_constants(
    model,
    network,
    root,
    width,
    height,
    row_entity,
    col_entity,
    row_label_callback,
    col_label_callback,
    col_dendro_callback
  );

  // fix for tooltip positioning
  el.style.position = 'relative';
  viz_state.el = el;

  set_mat_data(network, viz_state);

  viz_state.labels = {};
  viz_state.labels.clicks = {};
  // Term genes highlighted via a linked Enrich widget (blue row labels).
  // Enrich lowercases term genes; keep the set lowercased for matching.
  viz_state.labels.highlighted_genes = new Set(
    (model.get('highlighted_genes') || []).map((gene) =>
      String(gene).toLowerCase()
    )
  );
  viz_state.labels._row_style_rev = 0;
  viz_state.labels._col_style_rev = 0;
  // Matrix row index of the focused row (Enrich gene click or row search);
  // rendered as a bold label overlay.
  viz_state.labels.focused_row_index = null;
  // The double-clicked label the matrix is custom-sorted by (blue while the
  // sorted axis's order remains 'custom').
  viz_state.labels.reorder_driver = null;

  ini_zoom_data(viz_state);

  viz_state.mat.orders = {};

  set_row_label_data(network, viz_state);
  set_col_label_data(network, viz_state);

  // Rank views need `mat.orders` and `linkage` in place (it captures them as the
  // "all" stop), and has to run before `ini_dendro` so that opening at a reduced
  // `rank_dim` builds every layer against the view's geometry from the first
  // frame rather than snapping to it afterwards.
  ini_rank_views(viz_state, network);
  set_rank_view_state(
    viz_state,
    resolve_rank_view_level(viz_state, model.get('rank_dim'))
  );

  viz_state.cats = {};
  viz_state.cats.row_cat_data = [];
  viz_state.cats.col_cat_data = [];

  ini_dendro(viz_state);
  calc_dendro_polygons(viz_state, 'row');
  calc_dendro_polygons(viz_state, 'col');

  const layers_mat = {};
  layers_mat.mat_layer = ini_mat_layer(viz_state);
  layers_mat.row_label_layer = ini_row_label_layer(viz_state);
  layers_mat.row_label_focus_layer = ini_row_label_focus_layer(viz_state);
  layers_mat.col_label_layer = ini_col_label_layer(viz_state);
  layers_mat.row_cat_layer = ini_row_cat_layer(viz_state);
  layers_mat.col_cat_layer = ini_col_cat_layer(viz_state);
  layers_mat.row_dendro_layer = ini_dendro_layer(layers_mat, viz_state, 'row');
  layers_mat.col_dendro_layer = ini_dendro_layer(layers_mat, viz_state, 'col');

  initialize_matrix_crop(deck_mat, layers_mat, viz_state, {
    on_mode_change: () => {
      ini_views(viz_state);
      deck_mat.setProps({
        views: viz_state.views.views_list,
      });
    },
  });

  // Store references on viz_state for use by UI components (e.g., bar graph hover)
  viz_state.deck_mat = deck_mat;
  viz_state.layers_mat = layers_mat;
  viz_state.focus_row = (row_index) =>
    focus_matrix_row(deck_mat, layers_mat, viz_state, row_index);

  // ---------------------------------------------------------------------------
  // Body mode: heatmap/size/dotplot (square grid) vs composition (stacked bars).
  // Composition reuses the whole Clustergram (order, column attributes, labels,
  // reorder) and only swaps the body geometry + hides population-side chrome.
  // ---------------------------------------------------------------------------
  const set_body_mode = (mode) => {
    viz_state.mat.viz_mode = mode;

    // Leaf-position formula (composition vs. uniform heatmap spacing) is
    // keyed on viz_mode, which was just updated above, so this always
    // reflects the mode we're switching *into*.
    refresh_dendro_for_viz_mode(layers_mat, viz_state);

    if (mode === 'composition') {
      set_composition_colors(viz_state);
      viz_state.mat._comp_cache = null;
      layers_mat.mat_layer = ini_composition_layer(viz_state);
      set_mat_layer_onclick(deck_mat, layers_mat, viz_state);
      set_composition_layer_onhover(deck_mat, layers_mat, viz_state);

      // Populations are shown as colored bar segments (+ row labels where
      // they fit), so hide the row attribute strip. Both dendrograms behave
      // normally (visible only when their axis order is 'clust') — the row
      // dendrogram's leaves are now positioned from the rightmost bar's
      // actual segments (see refresh_dendro_for_viz_mode above).
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        visible: false,
      });
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'row');
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');

      refresh_row_label_visibility(layers_mat, viz_state);
    } else {
      clearTimeout(viz_state.mat._comp_hover_timer);
      viz_state.mat.comp_hover_row = null;

      apply_mat_encoding(viz_state);
      layers_mat.mat_layer = ini_mat_layer(viz_state);
      set_mat_layer_onclick(deck_mat, layers_mat, viz_state);
      set_mat_layer_onhover(deck_mat, layers_mat, viz_state);

      layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        visible: true,
      });
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        visible: true,
      });
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'row');
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');
    }

    // Row-label geometry and color rules differ between the square grid and
    // composition's stacked bars: rebuild the bold focus overlay and
    // re-trigger base label colors for the new mode.
    refresh_row_label_styles(layers_mat, viz_state);

    update_mode_button_visibility(viz_state);

    // Recompute the per-view zoomAxis lock (composition restricts zoom to
    // vertical-only; see views.js/on_view_state_change.js) so a live mode
    // switch takes effect immediately, not just after the next pan/zoom.
    ini_views(viz_state);

    deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
      views: viz_state.views.views_list,
    });
  };

  refresh_attribute_layers(deck_mat, layers_mat, viz_state);

  // ---------------------------------------------------------------------------
  // Category layer click/hover handlers
  // ---------------------------------------------------------------------------
  set_cat_layer_handlers(deck_mat, layers_mat, viz_state, 'row');
  set_cat_layer_handlers(deck_mat, layers_mat, viz_state, 'col');

  // ---------------------------------------------------------------------------
  // Deck init
  // ---------------------------------------------------------------------------
  ini_views(viz_state);
  const global_view_state = ini_view_state(viz_state);

  set_mat_layer_onclick(deck_mat, layers_mat, viz_state);
  set_mat_layer_onhover(deck_mat, layers_mat, viz_state);
  set_row_label_layer_onclick(deck_mat, layers_mat, viz_state);
  set_col_label_layer_onclick(deck_mat, layers_mat, viz_state);
  set_row_label_layer_onhover(deck_mat, layers_mat, viz_state);
  set_col_label_layer_onhover(deck_mat, layers_mat, viz_state);
  set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, 'row');
  set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, 'col');
  set_dendro_layer_onhover(deck_mat, layers_mat, viz_state, 'row');
  set_dendro_layer_onhover(deck_mat, layers_mat, viz_state, 'col');

  // Failsafe: deck.gl's own per-layer onHover(null) on pointer-leave can be
  // skipped in edge cases (moving fast across a viewport boundary, an
  // in-canvas DOM overlay swallowing the pointermove that would have
  // reported "left"), leaving a hover highlight — or a still-pending delayed
  // one, which would apply itself a moment later — stuck after the pointer
  // has actually left the widget. `root` is the same element deck.gl's own
  // EventManager listens on (`parent` in `ini_deck`), so this fires at
  // exactly the boundary deck.gl already tracks, just without depending on
  // its per-layer picking diff to get there.
  viz_state.root.addEventListener('pointerleave', () => {
    clear_composition_hover(deck_mat, layers_mat, viz_state);
    clear_dendro_hover(deck_mat, layers_mat, viz_state);
    clear_cat_hover(deck_mat, layers_mat, viz_state);
  });

  deck_mat.setProps({
    onViewStateChange: (params) =>
      on_view_state_change(params, deck_mat, layers_mat, viz_state),
    onDragStart: (info) => viz_state.crop.on_drag_start(info),
    onDrag: (info) => viz_state.crop.on_drag(info),
    onDragEnd: (info) => viz_state.crop.on_drag_end(info),
    getCursor: ({ isDragging }) => {
      if (viz_state.crop?.active) {
        return 'crosshair';
      }
      return isDragging ? 'grabbing' : 'pointer';
    },
    views: viz_state.views.views_list,
    initialViewState: global_view_state,
    getTooltip: (params) => get_tooltip(viz_state, params),
    layerFilter: layer_filter,
    layers: get_mat_layers_list(layers_mat),
  });

  const ui_container = make_matrix_ui_container(
    deck_mat,
    layers_mat,
    viz_state
  );

  el.appendChild(ui_container);
  el.appendChild(viz_state.root);

  initialize_attribute_editor(viz_state, deck_mat, layers_mat);
  initialize_attribute_labels(deck_mat, layers_mat, viz_state);

  // Refresh layers to include attribute labels
  deck_mat.setProps({
    layers: get_mat_layers_list(layers_mat),
  });

  // Activate composition body once all standard layers/labels exist.
  if (viz_state.mat.viz_mode === 'composition') {
    set_body_mode('composition');
  }

  // ---------------------------------------------------------------------------
  // JS -> PY sync: manual_cat + category_colors
  // ---------------------------------------------------------------------------
  const sync_axes_to_traitlets = () => {
    if (!viz_state.model) return;

    const row_store = viz_state.obs_store?.manual_cat?.row;
    const col_store = viz_state.obs_store?.manual_cat?.col;

    const payload = {
      row: row_store ? row_store.toExportPayload() : {},
      col: col_store ? col_store.toExportPayload() : {},
    };

    const json = JSON.stringify(payload);

    // Primary sources of truth for Python
    viz_state.model.set('manual_cat', json);
    viz_state.model.set(
      'category_colors',
      viz_state.attr.category_colors || {}
    );

    viz_state.model.save_changes();
  };

  // Apply manual defs for an axis, refresh layers/UI, optionally sync to Python
  const apply_manual_and_refresh = (axis, { sync = false } = {}) => {
    const applied = apply_manual_definitions_to_axis(viz_state, axis);
    if (!applied) return;

    update_label_display_names(viz_state, axis);
    refresh_attribute_layers(deck_mat, layers_mat, viz_state);

    if (sync) {
      sync_axes_to_traitlets();
    }
  };

  // Whenever the JS manual_cat stores change (editor/dendro/etc.), repaint + sync
  if (viz_state.obs_store?.manual_cat) {
    ['row', 'col'].forEach((axis) => {
      const manual_store = viz_state.obs_store.manual_cat[axis];
      if (!manual_store) return;

      manual_store.subscribe(
        () => {
          // Apply to JS state and then sync back to Python
          apply_manual_and_refresh(axis, { sync: true });
        },
        { immediate: false }
      );
    });
  }

  // ---------------------------------------------------------------------------
  // PYTHON -> JS one-way pieces
  //   - Names
  //   - Manual category config
  //   - category_colors seed
  //   - selected_genes / top_n_genes
  // ---------------------------------------------------------------------------
  if (viz_state.model) {
    // 1) Axis names
    viz_state.model.set(
      'row_names',
      viz_state.row_nodes.map((node) => String(node.name))
    );
    viz_state.model.set(
      'col_names',
      viz_state.col_nodes.map((node) => String(node.name))
    );
    viz_state.model.save_changes();

    // 2) ONE-TIME: manual categories bootstrap (PY -> JS), then sync back once
    const bootstrap_manual_categories = () => {
      viz_state.manual_cat = viz_state.manual_cat || { config: {}, flags: {} };

      // manual_cat_config may be JSON string or object
      const raw_config = viz_state.model.get('manual_cat_config');
      let parsed = raw_config;
      if (typeof parsed === 'string') {
        try {
          parsed = parsed ? JSON.parse(parsed) : {};
        } catch {
          parsed = {};
        }
      }

      const normalized =
        parsed && typeof parsed === 'object'
          ? parsed
          : { row: null, col: null };

      viz_state.manual_cat.config.row = normalized.row || null;
      viz_state.manual_cat.config.col = normalized.col || null;

      viz_state.manual_cat.flags = {
        row: !!viz_state.model.get('manual_row_cat'),
        col: !!viz_state.model.get('manual_col_cat'),
      };
      ['row', 'col'].forEach((axis) => {
        if (!viz_state.manual_cat.flags[axis]) return;

        const store = viz_state.obs_store?.manual_cat?.[axis];
        const attribute_name =
          viz_state.manual_cat.config?.[axis]?.attribute || null;

        if (store) {
          store.setAttribute(attribute_name);
        }

        // Build initial bars, but don't echo back yet
        apply_manual_and_refresh(axis, { sync: false });
      });

      // Let Python see the initial JS state (manual_cat + category_colors)
      sync_axes_to_traitlets();
    };

    bootstrap_manual_categories();

    // 3) Initial category_colors from Python (if any)
    const apply_category_colors = () => {
      viz_state.attr.category_colors =
        viz_state.model.get('category_colors') || {};
    };

    apply_category_colors();
    viz_state.model.on('change:category_colors', apply_category_colors);

    // 4) Misc other traitlets
    viz_state.model.on('change:selected_genes', () => {
      viz_state.obs_store.selected_genes.set(
        viz_state.model.get('selected_genes') || []
      );
    });

    viz_state.model.on('change:focused_gene', () => {
      const gene = viz_state.model.get('focused_gene') || '';
      if (gene) {
        viz_state.row_search?.focus(gene);
        return;
      }
      // Cleared focus (e.g. Enrich CLEAR): drop the bold overlay and un-hide
      // the base label underneath it.
      if (viz_state.labels.focused_row_index != null) {
        viz_state.labels.focused_row_index = null;
        refresh_row_label_styles(layers_mat, viz_state);
        deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
      }
    });

    viz_state.model.on('change:highlighted_genes', () => {
      viz_state.labels.highlighted_genes = new Set(
        (viz_state.model.get('highlighted_genes') || []).map((gene) =>
          String(gene).toLowerCase()
        )
      );
      refresh_row_label_highlight(deck_mat, layers_mat, viz_state);
    });

    const focused_gene = viz_state.model.get('focused_gene') || '';
    if (focused_gene) {
      viz_state.row_search?.focus(focused_gene);
    }

    viz_state.model.on('change:top_n_genes', () => {
      viz_state.top_n_genes = viz_state.model.get('top_n_genes') || 50;
    });

    viz_state.model.on('change:top_gene_percent', () => {
      viz_state.top_gene_percent =
        viz_state.model.get('top_gene_percent') || 10;
    });

    // Python-driven RANK view switch. `apply_rank_view` no-ops when the
    // resolved level is already active, so the value it echoes back into
    // `rank_dim` (after snapping) can't loop back around.
    viz_state.model.on('change:rank_dim', () => {
      const target = resolve_rank_view_level(
        viz_state,
        viz_state.model.get('rank_dim')
      );
      if (apply_rank_view(deck_mat, layers_mat, viz_state, target)) {
        viz_state.rank_view?.sync_control?.(target);
      }
    });

    // Live body-mode switch. Crossing the composition boundary rebuilds the
    // body layer (and toggles population-side chrome + legend); staying within
    // the square modes (heatmap/size/dotplot) just re-encodes + animates.
    viz_state.model.on('change:viz_mode', () => {
      const has_size_mat =
        viz_state.mat.max_size_value > 0 && !!network.size_mat;
      const old_mode = viz_state.mat.viz_mode;
      const new_mode = resolve_viz_mode(
        viz_state.model.get('viz_mode'),
        has_size_mat
      );

      const crossing =
        (old_mode === 'composition') !== (new_mode === 'composition');

      if (crossing) {
        set_body_mode(new_mode);
        return;
      }

      viz_state.mat.viz_mode = new_mode;

      if (new_mode === 'composition') {
        viz_state.mat._comp_cache = null;
        layers_mat.mat_layer = layers_mat.mat_layer.clone({
          updateTriggers: mat_reorder_triggers(viz_state),
        });
      } else {
        apply_mat_encoding(viz_state);
        const crop_sig = crop_filter_signature(viz_state);
        const fade_sig = crop_fade_signature(viz_state);
        layers_mat.mat_layer = layers_mat.mat_layer.clone({
          data: filter_matrix_data(viz_state),
          updateTriggers: {
            getPosition: crop_sig,
            getFillColor: [
              new_mode,
              crop_sig,
              fade_sig,
              viz_state.dendro?._highlight_rev || 0,
            ],
            getRadius: [new_mode, crop_sig],
          },
        });
      }
      update_mode_button_visibility(viz_state);
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
    });

    // Live proportion/count toggle for composition.
    viz_state.model.on('change:composition_normalized', () => {
      const value = viz_state.model.get('composition_normalized') !== false;
      viz_state.mat.composition_normalized = value;
      viz_state.mode_buttons?.normalized?.setActive(value);
      if (viz_state.mat.viz_mode !== 'composition') return;
      viz_state.mat._comp_cache = null;
      layers_mat.mat_layer = layers_mat.mat_layer.clone({
        updateTriggers: mat_reorder_triggers(viz_state),
      });
      refresh_row_label_visibility(layers_mat, viz_state);
      // Animated: the same leaves genuinely morph to a new row-dendrogram
      // position on a PROP/COUNTS toggle -- see dendro_transitions'
      // rationale in dendro_layers.js. Every other refresh_composition_dendro
      // call site (reorder, weight changes, viz-mode switch) leaves this
      // default (false) and snaps instantly instead.
      refresh_composition_dendro(layers_mat, viz_state, true);
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
    });

    // Live per-group weights (e.g. true dataset cell counts) for composition
    // "counts" mode bar height.
    viz_state.model.on('change:composition_col_weights', () => {
      viz_state.mat.composition_col_weights =
        viz_state.model.get('composition_col_weights') || {};
      if (viz_state.mat.viz_mode !== 'composition') return;
      viz_state.mat._comp_cache = null;
      layers_mat.mat_layer = layers_mat.mat_layer.clone({
        updateTriggers: mat_reorder_triggers(viz_state),
      });
      refresh_row_label_visibility(layers_mat, viz_state);
      refresh_composition_dendro(layers_mat, viz_state);
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
    });

    // Live DOT toggle: whether dotplot dot size encodes the secondary
    // (fraction) matrix, or is forced to a full tile.
    viz_state.model.on('change:dot_size_encoded', () => {
      const value = viz_state.model.get('dot_size_encoded') !== false;
      viz_state.mat.dot_size_encoded = value;
      viz_state.mode_buttons?.dot?.setActive(value);
      if (viz_state.mat.viz_mode !== 'dotplot') return;
      apply_mat_encoding(viz_state);
      const crop_sig = crop_filter_signature(viz_state);
      const fade_sig = crop_fade_signature(viz_state);
      layers_mat.mat_layer = layers_mat.mat_layer.clone({
        data: filter_matrix_data(viz_state),
        updateTriggers: {
          getPosition: crop_sig,
          getFillColor: [
            crop_sig,
            fade_sig,
            viz_state.dendro?._highlight_rev || 0,
          ],
          getRadius: [value, crop_sig],
        },
      });
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
    });

    const flushMatrixSliceRequest = () => {
      const req = viz_state.model.get('matrix_slice_request');
      if (!req || typeof req !== 'object') return;
      const reqId = req.req_id;
      if (!reqId || !req.op) return;

      const result = { req_id: reqId };
      let maxEntries;
      if (req.max_entries === undefined || req.max_entries === null) {
        maxEntries = undefined;
      } else {
        const n = Number(req.max_entries);
        maxEntries = Number.isFinite(n) ? n : undefined;
      }
      try {
        if (req.op === 'row') {
          const slice = buildRowAxisSlice(viz_state, req.index, maxEntries);
          if (slice) Object.assign(result, slice);
          else result.error = 'no_data';
        } else if (req.op === 'col') {
          const slice = buildColAxisSlice(viz_state, req.index, maxEntries);
          if (slice) Object.assign(result, slice);
          else result.error = 'no_data';
        } else if (req.op === 'cell') {
          const r = req.row;
          const c = req.col;
          const net = viz_state.mat?.net_mat;
          let val = null;
          if (net?.[r] && c >= 0 && c < net[r].length) {
            val = net[r][c];
          }
          Object.assign(result, buildCellSlice(r, c, val));
        } else if (req.op === 'row_col') {
          const r = req.row_index;
          const c = req.col_index;
          const slice = buildRowColPairSlice(viz_state, r, c, maxEntries);
          if (slice) Object.assign(result, slice);
          else result.error = 'no_data';
        } else {
          result.error = 'unknown_op';
        }
      } catch (e) {
        result.error = String(e?.message || e);
      }

      viz_state.model.set('matrix_slice_result', {});
      viz_state.model.set('matrix_slice_result', result);
      viz_state.model.save_changes();
    };

    viz_state.model.on('change:matrix_slice_request', flushMatrixSliceRequest);
  }

  const matrix = {
    obs_store: viz_state.obs_store,
    finalize: () => {
      deck_mat.finalize();
    },
  };

  return matrix;
};
