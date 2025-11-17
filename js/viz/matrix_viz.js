// The Celldega Matrix Vizualization Method is being built using the approaches
// and code adaptations from the Clustergrammer-GL library, which is available at
// github.com/ismms-himc/clustergrammer-gl
// and being used under the license
//
// MIT License

// Copyright (c) 2021 Nicolas Fernandez

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

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
} from '../deck-gl/matrix/cat_layers';
import { ini_deck } from '../deck-gl/matrix/deck_mat';
import {
  ini_dendro_layer,
  set_dendro_layer_onclick,
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
} from '../deck-gl/matrix/matrix_layers';
import { get_tooltip } from '../deck-gl/matrix/matrix_tooltip';
import { on_view_state_change } from '../deck-gl/matrix/on_view_state_change';
import { ini_views, ini_view_state } from '../deck-gl/matrix/views';
import { ini_zoom_data } from '../deck-gl/matrix/zoom';
import { calc_dendro_polygons, ini_dendro } from '../matrix/dendro';
import { set_row_label_data, set_col_label_data } from '../matrix/label_data';
import { set_mat_data } from '../matrix/mat_data';
import { set_mat_constants } from '../matrix/set_constants';
import {
  apply_attribute_frame,
  apply_manual_definitions_to_axis,
  refresh_attribute_layers,
  sync_manual_category_from_payload,
} from '../matrix/attr_state';
import { initialize_attribute_editor } from '../ui/attribute_editor';
import { make_matrix_ui_container } from '../ui/ui_containers';
import { create_category_breakdown } from '../ui/category_breakdown';

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
  // root.style.width = width
  const deck_mat = ini_deck(root, width, height);

  const viz_state = set_mat_constants(
    model,
    network,
    root,
    width,
    height,
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

  // need semicolon for some reason
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

  refresh_attribute_layers(deck_mat, layers_mat, viz_state);

  const attach_cat_handlers = (axis) => {
    const layer_key = `${axis}_cat_layer`;
    layers_mat[layer_key] = layers_mat[layer_key].clone({
      onClick: (event) => {
        if (!viz_state.attr?.editor?.open) {
          return;
        }

        const attr_index = event.object?.level;
        const node_index = event.object?.original_index;
        if (attr_index === undefined || node_index === undefined) {
          return;
        }

        const attr_name = viz_state.attr.names[axis]?.[attr_index];
        if (!attr_name) {
          return;
        }

        const node_name =
          axis === 'row'
            ? viz_state.row_nodes[node_index].name
            : viz_state.col_nodes[node_index].name;

        const attr_def = viz_state.attr.all_defs?.[axis]?.[attr_index];
        const value = event.object?.name;
        const color_key =
          value === null || value === undefined ? null : String(value);
        const color_hex = attr_def?.color_map?.[color_key] || null;

        viz_state.attr.editor.open({
          axis,
          selection: [node_name],
          attribute_name: attr_name,
          initial_value: value,
          initial_color: color_hex,
          position: event?.pixel
            ? { x: event.pixel[0], y: event.pixel[1] }
            : undefined,
        });
      },
    });
  };

  attach_cat_handlers('row');
  attach_cat_handlers('col');

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

  const category_breakdown = create_category_breakdown(viz_state);
  viz_state.category_breakdown = category_breakdown;
  if (viz_state.ui_breakdown_container) {
    viz_state.ui_breakdown_container.appendChild(
      category_breakdown.get_element()
    );
  }

  el.appendChild(ui_container);
  el.appendChild(viz_state.root);

  initialize_attribute_editor(viz_state, deck_mat, layers_mat);

  // --- SYNC HELPERS ------------------------------------------------------
  // Track when we're applying Python-originated changes so we don't
  // immediately echo them back to Python.
  viz_state.sync_suspended = false
  let bootstrap_done = false

  const with_sync_suspended = (fn) => {
    const prev = viz_state.sync_suspended
    viz_state.sync_suspended = true
    try {
      fn()
    } finally {
      viz_state.sync_suspended = prev
    }
  }

  // Single canonical sync: frames/colors + manual_cat
  const sync_axes_to_traitlets = (axes, { force = false } = {}) => {
    if (!viz_state.model) {
      return
    }
    // If we're in the middle of a Python->JS update, skip unless forced
    if (viz_state.sync_suspended && !force) {
      return
    }

    const axis_list = Array.isArray(axes) ? axes : [axes]

    // 1) Push the current JS attribute frames/colors back to Python
    axis_list.forEach((axis) => {
      const normalized = axis === 'col' ? 'col' : 'row'
      const frame = viz_state.attr.frames?.[normalized] || null
      const colors = viz_state.attr.color_payload?.[normalized] || {}

      viz_state.model.set(`${normalized}_attributes_df`, frame)
      viz_state.model.set(`${normalized}_attribute_colors`, colors)
    })

    // 1b) Also push global category_colors so Python can see all hexes
    viz_state.model.set(
      'category_colors',
      viz_state.attr.category_colors || {}
    )

    // 2) Push the manual_cat payload (used for the fine-grained per-id info)
    const row_store = viz_state.obs_store?.manual_cat?.row
    const col_store = viz_state.obs_store?.manual_cat?.col

    viz_state.manual_cat = viz_state.manual_cat || {}
    viz_state.manual_cat.self_update = true // mark as JS-originated

    viz_state.model.set(
      'manual_cat',
      JSON.stringify({
        row: row_store ? row_store.toExportPayload() : {},
        col: col_store ? col_store.toExportPayload() : {},
      })
    )

    viz_state.model.save_changes()
  }

  // Convenience helper so every "apply manual defs" path does the same thing
  const apply_manual_and_refresh = (axis, { sync = false } = {}) => {
    const applied = apply_manual_definitions_to_axis(viz_state, axis)
    if (!applied) {
      return
    }

    refresh_attribute_layers(deck_mat, layers_mat, viz_state)
    viz_state.category_breakdown?.update_available_attributes?.()

    if (sync) {
      sync_axes_to_traitlets(axis)
    }
  }







  if (viz_state.obs_store?.manual_cat) {
    ['row', 'col'].forEach((axis) => {
      const manual_store = viz_state.obs_store.manual_cat[axis]
      if (!manual_store) return

      manual_store.subscribe(
        () => {
          // User edited categories in JS (editor / dendro / etc.)
          apply_manual_and_refresh(axis, { sync: true })
        },
        { immediate: false }
      )
    })
  }









  if (viz_state.model) {

    const apply_row_attributes = () =>
      with_sync_suspended(() => {
        apply_attribute_frame(
          'row',
          viz_state.model.get('row_attributes_df'),
          viz_state.model.get('row_attribute_colors') || {},
          viz_state
        )
        apply_manual_and_refresh('row', { sync: false })
      })

    const apply_col_attributes = () =>
      with_sync_suspended(() => {
        apply_attribute_frame(
          'col',
          viz_state.model.get('col_attributes_df'),
          viz_state.model.get('col_attribute_colors') || {},
          viz_state
        )
        apply_manual_and_refresh('col', { sync: false })
      })

    viz_state.model.set(
      'row_names',
      viz_state.row_nodes.map((node) => String(node.name))
    );
    viz_state.model.set(
      'col_names',
      viz_state.col_nodes.map((node) => String(node.name))
    );
    viz_state.model.save_changes();

    apply_row_attributes();
    apply_col_attributes();

    viz_state.model.on('change:row_attributes_df', apply_row_attributes);
    viz_state.model.on('change:row_attribute_colors', apply_row_attributes);
    viz_state.model.on('change:col_attributes_df', apply_col_attributes);
    viz_state.model.on('change:col_attribute_colors', apply_col_attributes);

    const apply_manual_payload = () => {
      const payload = viz_state.model.get('manual_cat');

      if (viz_state.manual_cat?.self_update) {
        viz_state.manual_cat.self_update = false;
        return;
      }

      // For now we don't pull server manual_cat back into JS.
      // Once we implement a proper import on the stores, we can call
      // sync_manual_category_from_payload(payload, viz_state) here.
    };


    const apply_manual_config = () =>
      with_sync_suspended(() => {
        const raw_config = viz_state.model.get('manual_cat_config')
        let parsed = raw_config
        if (typeof parsed === 'string') {
          try {
            parsed = parsed ? JSON.parse(parsed) : {}
          } catch {
            parsed = {}
          }
        }

        const normalized =
          parsed && typeof parsed === 'object' ? parsed : { row: null, col: null }
        viz_state.manual_cat.config.row = normalized.row || null
        viz_state.manual_cat.config.col = normalized.col || null

        ;['row', 'col'].forEach((axis) => {
          const store = viz_state.obs_store?.manual_cat?.[axis]
          const attribute_name =
            viz_state.manual_cat?.config?.[axis]?.attribute || null
          if (store) {
            store.setAttribute(attribute_name)
          }
        })

        apply_manual_and_refresh('row', { sync: false })
        apply_manual_and_refresh('col', { sync: false })
      })

    const apply_manual_flags = () =>
      with_sync_suspended(() => {
        viz_state.manual_cat.flags = {
          row: !!viz_state.model.get('manual_row_cat'),
          col: !!viz_state.model.get('manual_col_cat'),
        }

        ;['row', 'col'].forEach((axis) => {
          if (!viz_state.manual_cat.flags?.[axis]) {
            return
          }
          const store = viz_state.obs_store?.manual_cat?.[axis]
          const attribute_name =
            viz_state.manual_cat?.config?.[axis]?.attribute || null
          if (store) {
            store.setAttribute(attribute_name)
          }
        })

        apply_manual_and_refresh('row', { sync: false })
        apply_manual_and_refresh('col', { sync: false })

        // ONE-TIME BOOTSTRAP: after Python turns manual_* on the first time,
        // push the JS-computed frames/colors + manual_cat back to Python.
        if (!bootstrap_done) {
          bootstrap_done = true
          sync_axes_to_traitlets(['row', 'col'], { force: true })
        }
      })



    const apply_category_colors = () =>
      with_sync_suspended(() => {
        viz_state.attr.category_colors =
          viz_state.model.get('category_colors') || {}
      })


    apply_manual_payload();
    apply_manual_config();
    apply_manual_flags();
    apply_category_colors();

    // One-time bootstrap sync so Python sees initial JS attribute state
    viz_state.manual_cat = viz_state.manual_cat || {};
    if (!viz_state.manual_cat.initial_seed_done) {
      sync_axes_to_traitlets(['row', 'col']);
      viz_state.manual_cat.initial_seed_done = true;
    }

    viz_state.model.on('change:manual_cat', apply_manual_payload);
    viz_state.model.on('change:manual_cat_config', apply_manual_config);
    viz_state.model.on('change:manual_row_cat', apply_manual_flags);
    viz_state.model.on('change:manual_col_cat', apply_manual_flags);
    viz_state.model.on('change:category_colors', apply_category_colors);


    viz_state.model.on('change:selected_genes', () => {
      viz_state.obs_store.selected_genes.set(
        viz_state.model.get('selected_genes') || []
      );
    });

    viz_state.model.on('change:top_n_genes', () => {
      viz_state.top_n_genes = viz_state.model.get('top_n_genes') || 50;
    });
  }

  const matrix = {
    obs_store: viz_state.obs_store,
    finalize: () => {
      viz_state.category_breakdown?.finalize?.();
      deck_mat.finalize();
    },
  };

  return matrix;
};
