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
  ini_row_cat_layer,
  ini_col_cat_layer,
  set_cat_layer_handlers,
} from '../deck-gl/matrix/cat_layers';
import { ini_composition_layer } from '../deck-gl/matrix/composition_layer';
import { ini_deck } from '../deck-gl/matrix/deck_mat';
import {
  ini_dendro_layer,
  set_dendro_layer_onclick,
  toggle_dendro_layer_visibility,
} from '../deck-gl/matrix/dendro_layers';
import {
  ini_row_label_layer,
  ini_col_label_layer,
  set_row_label_layer_onclick,
  set_col_label_layer_onclick,
} from '../deck-gl/matrix/label_layers';
import {
  ini_mat_layer,
  set_mat_layer_onclick,
} from '../deck-gl/matrix/mat_layer';
import {
  get_mat_layers_list,
  layer_filter,
  mat_reorder_triggers,
} from '../deck-gl/matrix/matrix_layers';
import { get_tooltip } from '../deck-gl/matrix/matrix_tooltip';
import { on_view_state_change } from '../deck-gl/matrix/on_view_state_change';
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

  ini_zoom_data(viz_state);

  viz_state.mat.orders = {};

  set_row_label_data(network, viz_state);
  set_col_label_data(network, viz_state);

  viz_state.cats = {};
  viz_state.cats.row_cat_data = [];
  viz_state.cats.col_cat_data = [];

  ini_dendro(viz_state);
  calc_dendro_polygons(viz_state, 'row');
  calc_dendro_polygons(viz_state, 'col');

  const layers_mat = {};
  layers_mat.mat_layer = ini_mat_layer(viz_state);
  layers_mat.row_label_layer = ini_row_label_layer(viz_state);
  layers_mat.col_label_layer = ini_col_label_layer(viz_state);
  layers_mat.row_cat_layer = ini_row_cat_layer(viz_state);
  layers_mat.col_cat_layer = ini_col_cat_layer(viz_state);
  layers_mat.row_dendro_layer = ini_dendro_layer(layers_mat, viz_state, 'row');
  layers_mat.col_dendro_layer = ini_dendro_layer(layers_mat, viz_state, 'col');

  // Store references on viz_state for use by UI components (e.g., bar graph hover)
  viz_state.deck_mat = deck_mat;
  viz_state.layers_mat = layers_mat;

  // ---------------------------------------------------------------------------
  // Body mode: heatmap/size/dotplot (square grid) vs composition (stacked bars).
  // Composition reuses the whole Clustergram (order, column attributes, labels,
  // reorder) and only swaps the body geometry + hides population-side chrome.
  // ---------------------------------------------------------------------------
  const set_body_mode = (mode) => {
    viz_state.mat.viz_mode = mode;

    if (mode === 'composition') {
      set_composition_colors(viz_state);
      viz_state.mat._comp_cache = null;
      layers_mat.mat_layer = ini_composition_layer(viz_state);
      set_mat_layer_onclick(deck_mat, layers_mat, viz_state);

      // Populations are shown as colored bar segments (+ row labels where
      // they fit), so hide the row attribute strip. The row dendrogram is
      // always meaningless here (rows aren't equal height once stacked), but
      // the column dendrogram should behave normally (visible only when col
      // order is 'clust').
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        visible: false,
      });
      layers_mat.row_dendro_layer = layers_mat.row_dendro_layer.clone({
        visible: false,
      });
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');

      refresh_row_label_visibility(layers_mat, viz_state);
    } else {
      apply_mat_encoding(viz_state);
      layers_mat.mat_layer = ini_mat_layer(viz_state);
      set_mat_layer_onclick(deck_mat, layers_mat, viz_state);

      layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        visible: true,
      });
      layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
        visible: true,
      });
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'row');
      toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');
    }

    update_mode_button_visibility(viz_state);
    deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
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
  set_row_label_layer_onclick(deck_mat, layers_mat, viz_state);
  set_col_label_layer_onclick(deck_mat, layers_mat, viz_state);
  set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, 'row');
  set_dendro_layer_onclick(deck_mat, layers_mat, viz_state, 'col');

  deck_mat.setProps({
    onViewStateChange: (params) =>
      on_view_state_change(params, deck_mat, layers_mat, viz_state),
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

    viz_state.model.on('change:top_n_genes', () => {
      viz_state.top_n_genes = viz_state.model.get('top_n_genes') || 50;
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
        layers_mat.mat_layer = layers_mat.mat_layer.clone({
          data: viz_state.mat.mat_data.slice(),
          updateTriggers: {
            getFillColor: new_mode,
            getRadius: new_mode,
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
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
    });

    // Live height/opacity encoding toggle for composition.
    viz_state.model.on('change:composition_encoding', () => {
      const value = viz_state.model.get('composition_encoding') || 'height';
      viz_state.mat.composition_encoding = value;
      viz_state.mode_buttons?.encoding?.setActive(value);
      if (viz_state.mat.viz_mode !== 'composition') return;
      viz_state.mat._comp_cache = null;
      layers_mat.mat_layer = layers_mat.mat_layer.clone({
        updateTriggers: mat_reorder_triggers(viz_state),
      });
      refresh_row_label_visibility(layers_mat, viz_state);
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
      layers_mat.mat_layer = layers_mat.mat_layer.clone({
        data: viz_state.mat.mat_data.slice(),
        updateTriggers: { getRadius: value },
      });
      deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
    });
  }

  const matrix = {
    obs_store: viz_state.obs_store,
    finalize: () => {
      deck_mat.finalize();
    },
  };

  return matrix;
};
