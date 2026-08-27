import { DrawPolygonMode, ViewMode } from '@deck.gl-community/editable-layers';
import * as d3 from 'd3';

import { toggle_background_layer_visibility } from '../deck-gl/layers/background_layer';
import { update_cell_pickable_state } from '../deck-gl/layers/cell_layer';
import {
  update_edit_layer_mode,
  calc_and_update_rgn_bar_graph,
  sync_region_to_model,
} from '../deck-gl/layers/edit_layer';
import { toggle_visibility_image_layers } from '../deck-gl/layers/image_layers';
import { build_nbhd_cloud_gene_bar_data } from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { toggle_nbhd_layer_visibility } from '../deck-gl/layers/nbhd_layer';
import { update_path_pickable_state } from '../deck-gl/layers/path_layer';
import { update_trx_pickable_state } from '../deck-gl/layers/trx_layer';
import { set_composition_normalized } from '../deck-gl/matrix/composition_layer';
import { update_dendro_layer_data } from '../deck-gl/matrix/dendro_layers';
import { set_dot_size_encoded } from '../deck-gl/matrix/mat_layer';
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import {
  uniprot_data,
  uniprot_get_request,
} from '../external_apis/uniprot_api';
import {
  is_orbit_technology,
  is_neighborhood_cloud_technology,
} from '../global_variables/image_info';
import {
  calc_dendro_triangles,
  calc_dendro_polygons,
  alt_slice_linkage,
} from '../matrix/dendro';
import { debounce } from '../utils/debounce';
import { refresh_layer } from '../utils/refresh_layer';

import {
  make_bar_graph,
  bar_callback_nbhd,
  bar_callback_nbhd_cloud_cluster,
  bar_callback_nbhd_cloud_slice,
  bar_callback_cat,
  make_bar_container,
  bar_callback_gene,
} from './bar_plot';
import { make_dataset_dropdown } from './dataset_dropdown';
import { set_gene_search } from './gene_search';
import { make_logo_button } from './logo';
import { init_matrix_cat_bars } from './matrix_cat_bars';
import {
  make_img_layer_slider_callback,
  toggle_slider,
  ini_slider,
  ini_slider_params,
} from './sliders';
import {
  apply_state_button_style,
  make_button,
  make_edit_button,
  make_reorder_button,
  make_text_toggle_group,
} from './text_buttons';

export const make_ui_container = () => {
  const ui_container = document.createElement('div');
  ui_container.style.display = 'flex';
  ui_container.style.flexDirection = 'row';
  ui_container.style.border = '1px solid #d3d3d3';
  ui_container.className = 'ui_container';
  ui_container.style.height = '100px';

  // ✅ CSS rules to prevent border cutoff
  ui_container.style.boxSizing = 'border-box';
  ui_container.style.width = '100%';
  ui_container.style.maxWidth = '100%';
  ui_container.style.margin = '0 auto';

  // The control panel's columns (IMG/CELL/TRX/etc.) have fixed pixel widths
  // and don't wrap. When the host page is narrower than their combined
  // width (e.g. embedded in a docs article column), scroll horizontally
  // instead of squeezing/overlapping the logo button pinned at the right
  // (see make_logo_button's flex-shrink:0).
  ui_container.style.overflowX = 'auto';

  return ui_container;
};

export const make_ctrl_container = () => {
  const ctrl_container = document.createElement('div');
  ctrl_container.style.display = 'flex';
  ctrl_container.style.flexDirection = 'row';
  ctrl_container.className = 'ctrl_container';
  // flex (not a hard width:100%) so it shares ui_container's width with the
  // non-shrinking logo button instead of competing with it for space.
  // min-width:0 lets it shrink below its content size so the *row* (not the
  // logo) is what scrolls when content is wider than the available space.
  ctrl_container.style.flex = '1 1 auto';
  ctrl_container.style.minWidth = '0';
  return ctrl_container;
};

export const flex_container = (class_name, flex_direction, height = null) => {
  const container = document.createElement('div');
  container.className = class_name;

  container.style.display = 'flex';
  container.style.flexDirection = flex_direction;

  if (height !== null) {
    container.style.height = `${height}px`;
    container.style.overflow = 'scroll';
  }

  return container;
};

export const make_slider_container = (class_name) => {
  const slider_container = document.createElement('div');
  slider_container.className = class_name;
  slider_container.style.width = '100%';
  slider_container.style.marginLeft = '2px';
  slider_container.style.marginTop = '2px';
  return slider_container;
};

/**
 * Get a short display name for an axis entity.
 * Returns "Row" or "Col" if no entity is specified or if entity is "N.A.".
 */
const get_axis_display_name = (viz_state, axis) => {
  const entity_info =
    axis === 'row' ? viz_state.row_entity : viz_state.col_entity;

  // Default to "Row" or "Col" if no entity or if entity is "N.A."
  const default_name = axis === 'row' ? 'Row' : 'Col';

  if (entity_info && entity_info.entity) {
    const { entity } = entity_info;

    // If entity is "N.A." or empty, use default axis name
    if (!entity || entity === 'N.A.' || entity === 'n.a.') {
      return default_name;
    }

    // Use abbreviated entity name for known types
    const abbrev = {
      gene: 'Gene',
      cell: 'Cell',
      nbhd: 'Nbhd',
      cluster: 'Clust',
      hextile: 'Hex',
      dataset: 'DSET',
      cell_population: 'POP',
    };
    return abbrev[entity] || entity.substring(0, 4).toUpperCase();
  }

  return default_name;
};

/**
 * Show/hide viz_mode-dependent control-panel chrome: the "TILE: PROP|UNIT"
 * and "PROP|COUNTS" toggles, and the row Dendro slider (never meaningful in
 * composition mode, since rows aren't equal height once stacked). Call after
 * any change to `viz_state.mat.viz_mode`.
 *
 * @param {object} viz_state - Visualization state.
 */
export const update_mode_button_visibility = (viz_state) => {
  const buttons = viz_state.mode_buttons;
  if (!buttons) return;

  const is_dotplot = viz_state.mat.viz_mode === 'dotplot';
  const is_composition = viz_state.mat.viz_mode === 'composition';

  buttons.dot.container.style.display = is_dotplot ? 'inline-flex' : 'none';
  buttons.normalized.container.style.display = is_composition
    ? 'inline-flex'
    : 'none';

  if (viz_state.dendro?.sliders?.row) {
    viz_state.dendro.sliders.row.style.display = is_composition ? 'none' : '';
  }
};

export const make_matrix_ui_container = (deck_mat, layers_mat, viz_state) => {
  const ui_container = make_ui_container();
  const ctrl_container = flex_container('button_container', 'column');
  // Never shrink/wrap ui_container's direct children -- with the row now
  // scrollable (see make_ui_container), squeezing these instead of
  // scrolling would visually corrupt the fixed-size logo button.
  ctrl_container.style.flexShrink = '0';

  const slider_container = flex_container('slider_container', 'column');
  slider_container.style.flexShrink = '0';

  // Button width for reorder controls (compact sizing).
  const button_width = 34;
  // Fixed label width (both axis rows use it) so reorder buttons start at
  // the same x position regardless of entity name length.
  const axis_label_width = 44;

  const axes = ['col', 'row'];

  const inst_orders = ['clust', 'sum', 'var', 'ini'];

  // Match the vertical rhythm of the Dendro slider pair (10px between the
  // two sliders) between the two reorder-button rows.
  const axis_row_margin_top = { col: '0px', row: '10px' };

  axes.forEach((axis) => {
    const inst_container = flex_container(axis, 'row');
    inst_container.style.alignItems = 'center';
    inst_container.style.marginTop = axis_row_margin_top[axis];

    // Use entity name if available. Non-clickable: black, plain text, no pill.
    const axis_label = get_axis_display_name(viz_state, axis);

    d3.select(inst_container)
      .append('div')
      .text(`${axis_label}:`)
      .style('flex', `0 0 ${axis_label_width}px`)
      .style('white-space', 'nowrap')
      .style('font-size', '9px')
      .style('font-weight', 'bold')
      .style('color', 'black')
      .style('user-select', 'none')
      .style(
        'font-family',
        '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
      );

    inst_orders.forEach((label) => {
      const isClust = label === 'clust';
      make_reorder_button(
        inst_container,
        label,
        isClust,
        button_width,
        axis,
        deck_mat,
        layers_mat,
        viz_state
      );
    });

    ctrl_container.appendChild(inst_container);
  });

  viz_state.dendro.sliders = {};

  const axis_has_crop_filter = (_viz_state, axis) =>
    Array.isArray(_viz_state.crop?.filter?.[axis]) &&
    _viz_state.crop.filter[axis].length > 0;

  const dendro_slider_callback = (_deck_mat, _viz_state, axis, event) => {
    if (axis_has_crop_filter(_viz_state, axis)) {
      event.target.value = _viz_state.dendro.sliders[`${axis}_percent`] ?? 50;
      return;
    }

    _viz_state.dendro.sliders[`${axis}_percent`] = event.target.value;

    // Update the dendrogram layer
    _viz_state.dendro.sliders[`${axis}_value`] =
      (_viz_state.dendro.max_linkage_dist[axis] * event.target.value) / 100;

    alt_slice_linkage(
      _viz_state,
      axis,
      _viz_state.dendro.sliders[`${axis}_value`]
    );
    calc_dendro_triangles(_viz_state, axis);
    calc_dendro_polygons(_viz_state, axis);
    update_dendro_layer_data(layers_mat, _viz_state, axis);

    _deck_mat.setProps({
      layers: get_mat_layers_list(layers_mat),
    });
  };

  axes.forEach((axis) => {
    const slider = document.createElement('input');
    viz_state.dendro.sliders[axis] = slider;

    const ini_dendro_value = 50;
    viz_state.dendro.sliders[`${axis}_percent`] = ini_dendro_value;

    ini_slider_params(slider, ini_dendro_value, (event) =>
      dendro_slider_callback(deck_mat, viz_state, axis, event)
    );
  });

  viz_state.dendro.sliders.col.style.marginTop = '3px';
  viz_state.dendro.sliders.row.style.marginTop = '10px';

  d3.select(slider_container)
    .append('div')
    .text('Dendro')
    .style('width', '40px')
    .style('height', '16px')
    .style('display', 'inline-flex')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('text-align', 'center')
    .style('cursor', 'pointer')
    .style('font-size', '10px')
    .style('font-weight', 'bold')
    .style('color', '#47515b')
    .style('border', '2px solid')
    .style('border-color', 'white')
    .style('border-radius', '8px')
    .style('margin-left', '10px')
    .style('user-select', 'none')
    .style(
      'font-family',
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
    );

  slider_container.appendChild(viz_state.dendro.sliders.col);
  slider_container.appendChild(viz_state.dendro.sliders.row);

  // add top margin to ctrl_container and slider_container
  ctrl_container.style.marginTop = '10px';
  // Small gap so the entity-title label (e.g. "DSET:") isn't flush against
  // the control panel's left border.
  ctrl_container.style.marginLeft = '6px';
  slider_container.style.marginTop = '0px';
  slider_container.style.marginLeft = '5px';

  ui_container.appendChild(ctrl_container);
  ui_container.appendChild(slider_container);

  // ---------------------------------------------------------------------
  // Body-mode toggles: TILE: PROP|UNIT (dotplot only) and PROP|COUNTS
  // (composition only). Mounted to the right of the reorder buttons, always
  // present but shown/hidden per `viz_mode` (see `update_mode_button_visibility`).
  // ---------------------------------------------------------------------
  const mode_container = flex_container('mode_container', 'row');
  // Top-align with the first reorder-button row (ctrl_container's own
  // marginTop, below), not vertically centered against the taller sibling
  // columns to its left.
  mode_container.style.alignItems = 'flex-start';
  mode_container.style.marginTop = '10px';
  mode_container.style.marginLeft = '10px';
  mode_container.style.flexShrink = '0';

  // Titled group wrapper (e.g. "TILE:" + a toggle group), shown/hidden as one
  // unit so a title never dangles without its buttons.
  const make_titled_group = (title, build_group) => {
    const wrapper = document.createElement('div');
    wrapper.style.display = 'inline-flex';
    wrapper.style.alignItems = 'center';
    mode_container.appendChild(wrapper);

    d3.select(wrapper)
      .append('div')
      .text(title)
      .style('font-size', '9px')
      .style('font-weight', 'bold')
      .style('color', 'black')
      .style(
        'font-family',
        '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
      );

    const group = build_group(wrapper);
    group.container.style.marginLeft = '4px';
    return { wrapper, group };
  };

  // dot_size_encoded: true -> size encodes the fraction/dot matrix ("PROP"),
  // false -> forced to a full, unit-scaled tile ("UNIT").
  const { wrapper: dot_wrapper, group: dot_toggle } = make_titled_group(
    'TILE:',
    (container) =>
      make_text_toggle_group(
        container,
        [
          { label: 'prop', value: true },
          { label: 'unit', value: false },
        ],
        viz_state.mat.dot_size_encoded,
        (value) => set_dot_size_encoded(deck_mat, layers_mat, viz_state, value),
        viz_state
      )
  );

  const normalized_toggle = make_text_toggle_group(
    mode_container,
    [
      { label: 'prop', value: true },
      { label: 'counts', value: false },
    ],
    viz_state.mat.composition_normalized,
    (value) =>
      set_composition_normalized(deck_mat, layers_mat, viz_state, value),
    viz_state
  );
  normalized_toggle.container.style.marginLeft = '10px';

  viz_state.mode_buttons = {
    dot: { container: dot_wrapper, setActive: dot_toggle.setActive },
    normalized: normalized_toggle,
  };
  update_mode_button_visibility(viz_state);

  ui_container.appendChild(mode_container);

  const crop_container = flex_container('crop_container', 'row');
  crop_container.style.alignItems = 'flex-start';
  crop_container.style.marginTop = '10px';
  crop_container.style.marginLeft = '10px';
  crop_container.style.flexShrink = '0';

  const crop_button = d3
    .select(crop_container)
    .append('div')
    .text('CROP')
    .style('display', 'inline-flex')
    .style('font-size', '9px')
    .style(
      'font-family',
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
    )
    .on('click', () => {
      viz_state.crop?.toggle();
    });

  const undo_button = d3
    .select(crop_container)
    .append('div')
    .text('UNDO')
    .style('display', 'inline-flex')
    .style('font-size', '9px')
    .style('margin-left', '10px')
    .style(
      'font-family',
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
    )
    .on('click', () => {
      viz_state.crop?.undo();
    });

  viz_state.crop?.set_controls({
    set_active: (active) => {
      apply_state_button_style(crop_button, active, viz_state);
    },
    set_crop_enabled: (enabled) => {
      crop_button
        .style('opacity', enabled ? 1 : 0.55)
        .style('pointer-events', enabled ? 'auto' : 'none');
    },
    set_undo_enabled: (enabled) => {
      apply_state_button_style(undo_button, enabled, viz_state)
        .style('opacity', enabled ? 1 : 0.55)
        .style('pointer-events', enabled ? 'auto' : 'none');
    },
  });

  ui_container.appendChild(crop_container);

  // Initialize category bar graphs (shown on dendro click)
  init_matrix_cat_bars(viz_state, ui_container);

  // === Add logo to top right === //
  ui_container.appendChild(make_logo_button('clustergram'));

  return ui_container;
};

export const make_ist_ui_container = (
  dataset_name,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const ui_container = make_ui_container();
  const ctrl_container = make_ctrl_container();

  viz_state.containers.image = flex_container('image_container', 'column');

  const img_layers_container = flex_container(
    'img_layers_container',
    'column',
    72
  );
  img_layers_container.style.width = '135px';
  img_layers_container.style.border = '1px solid #d3d3d3';
  img_layers_container.style.marginTop = '3px';
  img_layers_container.style.marginLeft = '2px';

  img_layers_container.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } = img_layers_container;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  const bar_container_width = '115px';

  const cell_container = flex_container('cell_container', 'column');
  // widths are custom because of the length of the text buttons varies
  cell_container.style.width = bar_container_width;
  const cell_ctrl_container = flex_container('cell_ctrl_container', 'row');
  cell_ctrl_container.style.marginLeft = '0px';

  // gene container will contain trx button/slider and gene search
  const gene_container = flex_container('gene_container', 'column');
  gene_container.style.marginTop = '0px';
  gene_container.style.width = bar_container_width;
  const trx_container = flex_container('trx_container', 'row');

  // neighborhood-cloud repurposes the CELL slot itself (button relabeled
  // "NBHD", radius slider dropped in favor of the opacity slider) rather
  // than building a separate NBHD section -- see the cell_ctrl_container
  // block below. The legacy 2D nbhd feature still gets its own section.
  const nbhdControlsEnabled = viz_state.nbhd.is_nbhd && !viz_state.nbhd.edit;

  let nbhd_container;
  let nbhd_ctrl_container;
  if (viz_state.nbhd.is_nbhd) {
    nbhd_container = flex_container('nbhd_container', 'column');
    nbhd_container.style.width = bar_container_width;
    nbhd_ctrl_container = flex_container('nbhd_ctrl_container', 'row');
    nbhd_ctrl_container.style.marginLeft = '0px';
    nbhd_ctrl_container.style.height = '22.5px';
  }

  let nbhd_cloud_slice_container;
  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    nbhd_cloud_slice_container = flex_container(
      'nbhd_cloud_slice_container',
      'column'
    );
    nbhd_cloud_slice_container.style.width = bar_container_width;
  }

  const cell_slider_container = make_slider_container('cell_slider_container');
  const trx_slider_container = make_slider_container('trx_slider_container');
  let nbhd_slider_container;
  if (nbhdControlsEnabled) {
    nbhd_slider_container = make_slider_container('nbhd_slider_container');
  }

  const { technology } = viz_state.img.landscape_parameters;
  const isChromium = technology === 'Chromium';
  const isPointCloud = is_orbit_technology(technology);

  // Registered unconditionally (not just for non-orbit technologies) so that
  // `viz_state.obs_store.viz_background_layer.set(false)` (set early in
  // landscape_ist.js for any technology without an image layer, including
  // point-cloud/neighborhood-cloud) actually takes effect. Without this, the
  // background layer's default `visible: true` stands, and its solid black
  // fill polygon (background_layer.js) never gets hidden for orbit
  // technologies.
  viz_state.obs_store.viz_background_layer.subscribe((visible) => {
    toggle_background_layer_visibility(layers_obj, visible);
    refresh_layer(viz_state, layers_obj, 'background_layer');
  });

  // Hide the gene panel (gene bar graph + gene search) for gene-less datasets
  // (e.g. a point-cloud DegaFiles written without cbg data). set_meta_gene has
  // already run, so an empty gene_names array reliably signals "no genes".
  const hasGenes = (viz_state.genes.gene_names?.length || 0) > 0;

  if (!isPointCloud) {
    const spatial_toggle_container = flex_container(
      'image_layer_container',
      'row'
    );

    if (isChromium) {
      make_button(
        spatial_toggle_container,
        'ist',
        'UMAP',
        'blue',
        35,
        'button',
        deck_ist,
        layers_obj,
        viz_state
      );
    } else {
      if (viz_state.umap.has_umap === true) {
        const umap_active = viz_state.obs_store.umap_state.get();
        let ini_umap_color;
        let ini_spatial_color;

        if (umap_active === true) {
          ini_umap_color = 'blue';
          ini_spatial_color = 'gray';
        } else {
          ini_umap_color = 'gray';
          ini_spatial_color = 'blue';
        }

        make_button(
          spatial_toggle_container,
          'ist',
          'UMAP',
          ini_umap_color,
          35,
          'button',
          deck_ist,
          layers_obj,
          viz_state
        );
        make_button(
          spatial_toggle_container,
          'ist',
          'SPATIAL',
          ini_spatial_color,
          50,
          'button',
          deck_ist,
          layers_obj,
          viz_state
        );
      }

      make_button(
        spatial_toggle_container,
        'ist',
        'IMG',
        'blue',
        30,
        'button',
        deck_ist,
        layers_obj,
        viz_state
      );
    }

    viz_state.containers.image.appendChild(spatial_toggle_container);

    // Add dataset dropdown if multiple datasets are available
    const dataset_dropdown = make_dataset_dropdown(
      viz_state,
      deck_ist,
      layers_obj
    );
    if (dataset_dropdown) {
      spatial_toggle_container.appendChild(dataset_dropdown);
    }

    const get_slider_by_name = (img, name) => {
      return img.image_layer_sliders.filter((slider) => slider.name === name);
    };

    const make_img_layer_ctrl = (img, inst_image) => {
      const inst_name = inst_image.button_name;

      const inst_container = flex_container('image_layer_container', 'row');
      inst_container.style.height = '21px';

      const ini_img_color = viz_state.obs_store.umap_state.get()
        ? 'gray'
        : 'blue';

      make_button(
        inst_container,
        'ist',
        inst_name,
        ini_img_color,
        75,
        'img_layer_button',
        deck_ist,
        layers_obj,
        viz_state
      );

      const inst_slider_container = make_slider_container(inst_name);

      const slider = get_slider_by_name(img, inst_name)[0];

      const img_layer_slider_callback = make_img_layer_slider_callback(
        inst_name,
        deck_ist,
        layers_obj,
        viz_state
      );

      const debounce_time = 100;
      const img_layer_slider_callback_debounced = debounce(
        img_layer_slider_callback,
        debounce_time
      );
      const ini_img_slider_value = 50;
      ini_slider_params(
        slider,
        ini_img_slider_value,
        img_layer_slider_callback_debounced
      );

      inst_slider_container.appendChild(slider);

      inst_container.appendChild(inst_slider_container);

      img_layers_container.appendChild(inst_container);
    };

    viz_state.img.image_info.map((inst_image) =>
      make_img_layer_ctrl(viz_state.img, inst_image)
    );

    viz_state.obs_store.viz_image_layers.subscribe((viz_image_layers) => {
      d3.select(viz_state.containers.image)
        .selectAll('.img_layer_button')
        .style('color', viz_image_layers ? 'blue' : 'gray');

      viz_state.img.image_layer_sliders.map((slider) =>
        toggle_slider(slider, viz_image_layers)
      );

      toggle_visibility_image_layers(layers_obj, viz_image_layers);

      refresh_layer(viz_state, layers_obj, 'image_layers');

      // move out of umap state if image is visible
      if (viz_image_layers && viz_state.obs_store.umap_state.get()) {
        viz_state.obs_store.landscape_view.set('spatial');
      }
    });

    viz_state.obs_store.viz_nbhd_layer.subscribe((visible) => {
      toggle_nbhd_layer_visibility(layers_obj, visible);
      refresh_layer(viz_state, layers_obj, 'nbhd_layer');
    });

    viz_state.containers.image.appendChild(img_layers_container);
  }

  // neighborhood-cloud repurposes this slot: "NBHD" (shapes show/hide)
  // instead of "CELL" (per-cell radius, meaningless here -- cells only ever
  // appear on demand for one selected neighborhood, via nbhd_cloud_cell_layer).
  // Starts blue/active either way, matching each layer's actual starting
  // visibility (shapes visible by default, same as the legacy CELL layer).
  make_button(
    cell_ctrl_container,
    'ist',
    viz_state.nbhd_cloud?.is_nbhd_cloud ? 'NBHD' : 'CELL',
    'blue',
    40,
    'button',
    deck_ist,
    layers_obj,
    viz_state
  );

  if (nbhdControlsEnabled) {
    make_button(
      nbhd_ctrl_container,
      'ist',
      'NBHD',
      'gray',
      40,
      'button',
      deck_ist,
      layers_obj,
      viz_state
    );
  }

  make_button(
    trx_container,
    'ist',
    'TRX',
    'blue',
    40,
    'button',
    deck_ist,
    layers_obj,
    viz_state
  );

  viz_state.sliders = {};

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    // No per-cell radius control here (cells only appear on demand, per
    // selected neighborhood, via nbhd_cloud_cell_layer) -- the opacity
    // slider takes this slot instead.
    ini_slider('nbhd', deck_ist, layers_obj, viz_state);
    cell_slider_container.appendChild(viz_state.sliders.nbhd);
    cell_ctrl_container.appendChild(cell_slider_container);
    toggle_slider(viz_state.sliders.nbhd, true);
  } else {
    ini_slider('cell', deck_ist, layers_obj, viz_state);
    cell_slider_container.appendChild(viz_state.sliders.cell);
    cell_ctrl_container.appendChild(cell_slider_container);
  }

  // Only add the regular nbhd slider when NOT in edit mode
  // For edit mode, we'll add a separate opacity slider later (after buttons)
  if (nbhdControlsEnabled) {
    ini_slider('nbhd', deck_ist, layers_obj, viz_state);
    nbhd_slider_container.appendChild(viz_state.sliders.nbhd);
    nbhd_ctrl_container.appendChild(nbhd_slider_container);
    // neighborhood-cloud has no "exclusive active layer" concept (shapes and
    // cells coexist via the continuous zoom crossfade) -- the slider should
    // just start enabled, not tied to the legacy viz_nbhd_layer toggle.
    toggle_slider(
      viz_state.sliders.nbhd,
      viz_state.nbhd_cloud?.is_nbhd_cloud
        ? true
        : viz_state.obs_store.viz_nbhd_layer.get()
    );
  }

  viz_state.containers.bar_cluster = make_bar_container();

  viz_state.cats.svg_bar_cluster = d3.create('svg');
  viz_state.genes.svg_bar_gene = d3.create('svg');

  if (viz_state.nbhd.is_nbhd) {
    viz_state.nbhd.svg_bar_nbhd = d3.create('svg');
  }

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    // Repurposes the CELL slot's bar graph (the per-cell cluster-count bar
    // makes no sense here -- there's no per-cell data loaded up front) into
    // a per-cluster bar: one bar per cluster, area summed across every
    // slice's instance of it, colored by that cluster's real color.
    // Selecting a cluster (bar click or shape click) applies across every
    // slice at once, not just one (slice, cluster) instance.
    viz_state.nbhd_cloud.svg_bar_cluster = d3.create('svg');

    const areaByCluster = new Map();
    viz_state.nbhd_cloud.meta_neighborhood.forEach((nb) => {
      const clusterId = String(nb.cluster_id);
      areaByCluster.set(
        clusterId,
        (areaByCluster.get(clusterId) ?? 0) + nb.area
      );
    });
    const clusterBarData = Array.from(areaByCluster, ([clusterId, area]) => ({
      name: clusterId,
      value: area,
    }));
    const clusterColorDict = viz_state.cats.color_dict_cluster;

    make_bar_graph(
      viz_state.containers.bar_cluster,
      bar_callback_nbhd_cloud_cluster,
      viz_state.nbhd_cloud.svg_bar_cluster,
      clusterBarData,
      clusterColorDict,
      deck_ist,
      layers_obj,
      viz_state
    );
  } else {
    make_bar_graph(
      viz_state.containers.bar_cluster,
      bar_callback_cat,
      viz_state.cats.svg_bar_cluster,
      viz_state.cats.cluster_counts,
      viz_state.cats.color_dict_cluster,
      deck_ist,
      layers_obj,
      viz_state
    );
  }

  viz_state.containers.bar_gene = make_bar_container();

  // only keep the top 100 genes in gene_counts
  const max_num_gene_bars = 1000;
  viz_state.genes.gene_counts = viz_state.genes.gene_counts
    .sort((a, b) => b.value - a.value)
    .slice(0, max_num_gene_bars);

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    // Only genes with a shape (available_gene_shapes) or cell scatter
    // (available_gene_scatter) actually do anything when selected
    // (select_nbhd_cloud_gene) -- listing the generic top-gene panel here
    // would give ~100 bars that are all silent no-ops. Both kinds render
    // the same flat red in the bar itself (see build_nbhd_cloud_gene_bar_data).
    const geneColorDict = Object.fromEntries(
      [
        ...(viz_state.nbhd_cloud.available_gene_scatter ?? new Map()),
        ...(viz_state.nbhd_cloud.available_gene_shapes ?? new Map()),
      ].map(([gene]) => [gene, [255, 0, 0]])
    );

    make_bar_graph(
      viz_state.containers.bar_gene,
      bar_callback_gene,
      viz_state.genes.svg_bar_gene,
      build_nbhd_cloud_gene_bar_data(viz_state.nbhd_cloud),
      geneColorDict,
      deck_ist,
      layers_obj,
      viz_state
    );
  } else {
    make_bar_graph(
      viz_state.containers.bar_gene,
      bar_callback_gene,
      viz_state.genes.svg_bar_gene,
      viz_state.genes.top_gene_counts,
      viz_state.genes.color_dict_gene,
      deck_ist,
      layers_obj,
      viz_state
    );
  }

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    viz_state.nbhd_cloud.svg_bar_slice = d3.create('svg');
    viz_state.containers.bar_slice = make_bar_container();

    const sliceBarData = viz_state.nbhd_cloud.meta_slice.map((s) => ({
      name: s.slice_id,
      value: s.cell_count,
    }));
    const sliceColorDict = Object.fromEntries(
      sliceBarData.map((bar) => [bar.name, [136, 136, 136]])
    );

    make_bar_graph(
      viz_state.containers.bar_slice,
      bar_callback_nbhd_cloud_slice,
      viz_state.nbhd_cloud.svg_bar_slice,
      sliceBarData,
      sliceColorDict,
      deck_ist,
      layers_obj,
      viz_state
    );
  }

  const make_bar_cat_subscriber = (svg, container) => {
    return (selected_cats) => {
      // --- 1. Update the styles ---
      if (!Array.isArray(selected_cats) || selected_cats.length === 0) {
        svg.selectAll('g').attr('font-weight', 'normal').attr('opacity', 1.0);

        // Scroll to top if we're resetting
        container.scrollTo({
          top: 0,
          behavior: 'smooth',
        });
      } else {
        svg
          .selectAll('g')
          .attr('font-weight', (d) =>
            selected_cats.includes(d.name) ? 'bold' : 'normal'
          )
          .attr('opacity', (d) => (selected_cats.includes(d.name) ? 1.0 : 0.2));

        // --- 2. Scroll to the selected bar if only one is selected ---
        if (selected_cats.length === 1) {
          const inst_cat = selected_cats[0];

          const selectedBar = svg.selectAll('g').filter(function () {
            return d3.select(this).select('text').text() === inst_cat;
          });

          if (!selectedBar.empty()) {
            const barElement = selectedBar.node();
            const containerRect = container.getBoundingClientRect();
            const barRect = barElement.getBoundingClientRect();

            const barTop = barRect.top;
            const barBottom = barRect.bottom;
            const containerTop = containerRect.top;
            const containerBottom = containerRect.bottom;

            const barFullyVisible =
              barTop >= containerTop && barBottom <= containerBottom;

            if (!barFullyVisible) {
              const offsetTop = barTop - containerTop;
              const scrollTop = container.scrollTop + offsetTop;

              container.scrollTo({
                top: scrollTop,
                behavior: 'smooth',
              });
            }
          }
        }
      }
    };
  };

  viz_state.obs_store.selected_cats.subscribe(
    make_bar_cat_subscriber(
      viz_state.cats.svg_bar_cluster,
      viz_state.containers.bar_cluster
    ),
    { immediate: false }
  );

  viz_state.obs_store.selected_genes.subscribe(
    make_bar_cat_subscriber(
      viz_state.genes.svg_bar_gene,
      viz_state.containers.bar_gene
    ),
    { immediate: false }
  );

  const subscriber_new_bar_data =
    ({ svg, color_dict, selected_array, bar_callback, container }) =>
    (bar_data) => {
      const bar_height = 15;
      const svg_height = bar_height * (bar_data.length + 1);
      svg.attr('height', svg_height);

      const max_bar_width = 90;
      const bar_data_values = bar_data.map((d) => d.value);

      const y_scale = d3
        .scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, (bar_height + 1) * bar_data_values.length]);

      const x_scale = d3
        .scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, max_bar_width]);

      const bars = svg.selectAll('g').data(bar_data, (d) => d.name);

      // Enter new bars
      const bars_enter = bars
        .enter()
        .append('g')
        .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`)
        .on('click', (event, d) =>
          bar_callback(event, d, deck_ist, layers_obj, viz_state)
        );

      bars_enter
        .append('rect')
        .attr('width', 0)
        .attr('height', y_scale.bandwidth() - 1)
        .transition()
        .duration(750)
        .attr('width', (d) => x_scale(d.value));

      bars_enter
        .append('text')
        .attr('fill', 'black')
        .attr('x', '5px')
        .attr('y', y_scale.bandwidth() / 2 - 1)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'start')
        .attr('opacity', 0)
        .text((d) => d.name)
        .transition()
        .duration(750)
        .attr('opacity', 1);

      // Merge enter and update selections
      const bars_merged = bars.merge(bars_enter);

      // Update bars
      bars_merged
        .transition()
        .duration(750)
        .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`);

      bars_merged
        .select('rect')
        .attr('width', (d) => x_scale(d.value))
        .attr('fill', (d) => {
          const rgb = color_dict[d.name] || [0, 0, 0];
          const opacity =
            selected_array.length === 0 || selected_array.includes(d.name)
              ? 1
              : 0.1;
          return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${opacity})`;
        });

      bars_merged.select('text').text((d) => d.name);

      // Remove old bars
      bars.exit().transition().duration(750).attr('opacity', 0).remove();

      // Optional: scroll container to top
      if (container && !viz_state.close_up) {
        container.scrollTo({
          top: 0,
          behavior: 'smooth',
        });
      }
    };

  viz_state.obs_store.new_cell_bar_data.subscribe(
    subscriber_new_bar_data({
      svg: viz_state.cats.svg_bar_cluster,
      color_dict: viz_state.cats.color_dict_cluster,
      selected_array: viz_state.cats.selected_cats,
      bar_callback: bar_callback_cat,
      container: viz_state.containers.bar_cluster,
    }),
    { immediate: false }
  );

  viz_state.obs_store.new_gene_bar_data.subscribe(
    subscriber_new_bar_data({
      svg: viz_state.genes.svg_bar_gene,
      color_dict: viz_state.genes.color_dict_gene,
      selected_array: viz_state.genes.selected_genes,
      bar_callback: bar_callback_gene,
      container: viz_state.containers.bar_gene,
    }),
    { immediate: false }
  );

  cell_container.appendChild(cell_ctrl_container);
  cell_container.appendChild(viz_state.containers.bar_cluster);

  ini_slider('trx', deck_ist, layers_obj, viz_state);
  trx_container.appendChild(trx_slider_container);
  trx_slider_container.appendChild(viz_state.sliders.trx);

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    // Cluster-color mode is the initial state -- the repurposed TRX slider
    // (gene-shapes opacity) has nothing to control until a gene is
    // selected, so it starts disabled (sync_nbhd_cloud_opacity_sliders,
    // bar_plot.js, flips this once a gene is picked).
    toggle_slider(viz_state.sliders.trx, false);
  }

  gene_container.appendChild(trx_container);
  gene_container.appendChild(viz_state.containers.bar_gene);

  set_gene_search('ist', deck_ist, layers_obj, viz_state);

  viz_state.genes.gene_search.style.marginLeft = '0px';

  // add subscriber for gene search and gene_text_box
  viz_state.obs_store.selected_genes.subscribe(async (selected_genes) => {
    // if selected_genes has a length of 1, update the gene search input
    if (selected_genes.length === 1) {
      const inst_gene = selected_genes[0];

      viz_state.genes.gene_search_input.value = inst_gene;

      if (inst_gene !== '') {
        if (viz_state.genes.gene_names.includes(inst_gene)) {
          viz_state.genes.gene_text_box.textContent = 'loading';
          await uniprot_get_request(inst_gene);
          const gene_data = uniprot_data[inst_gene];

          if (gene_data && gene_data.name && gene_data.description) {
            viz_state.genes.gene_text_box.innerHTML = `<span style="color: blue;">${gene_data.name}</span><br>${gene_data.description}`;
          } else {
            viz_state.genes.gene_text_box.textContent = '';
          }
        }
      } else {
        viz_state.genes.gene_text_box.textContent = '';
      }

      viz_state.genes.gene_text_box.scrollTo({
        top: 0,
        behavior: 'smooth',
      });
    } else if (selected_genes.length === 0) {
      viz_state.genes.gene_search_input.value = '';
      viz_state.genes.gene_text_box.textContent = '';
    }
  });

  ui_container.appendChild(ctrl_container);

  if (!isPointCloud) {
    ctrl_container.appendChild(viz_state.containers.image);
  }
  ctrl_container.appendChild(cell_container);
  if (hasGenes) {
    ctrl_container.appendChild(gene_container);
  }

  viz_state.genes.gene_search.style.width = '160px';
  viz_state.genes.gene_search.style.marginLeft = '5px';

  // const sketch_callback = (event, _deck_ist, _layers_obj, _viz_state) => {
  //   const current = d3.select(event.currentTarget);
  //   const is_active = current.classed('active');
  //   // let button_name = current.text().toLowerCase()

  //   // clicking sketch should always return the rgn to visible
  //   _viz_state.edit.visible = true;
  //   current.classed('active', _viz_state.edit.visible).style('color', 'blue');

  //   d3.select(_viz_state.edit.buttons.rgn)
  //     .style('color', 'blue')
  //     .classed('active', true);

  //   update_edit_visitility(_layers_obj, _viz_state.edit.visible);

  //   if (is_active === false) {
  //     current.classed('active', true).style('color', 'blue');

  //     _viz_state.edit.mode = 'sktch';

  //     update_edit_layer_mode(_layers_obj, DrawPolygonMode);
  //     update_cell_pickable_state(_layers_obj, false);
  //     update_path_pickable_state(_layers_obj, false);
  //     update_trx_pickable_state(_layers_obj, false);
  //     const layers_list = get_layers_list(_layers_obj, _viz_state.close_up);
  //     _deck_ist.setProps({ layers: layers_list });
  //   } else if (is_active === true) {
  //     _viz_state.edit.mode = 'view';

  //     current.classed('active', false).style('color', 'gray');

  //     update_edit_layer_mode(_layers_obj, ViewMode);
  //     update_cell_pickable_state(_layers_obj, true);
  //     update_path_pickable_state(_layers_obj, true);
  //     update_trx_pickable_state(_layers_obj, true);

  //     const layers_list = get_layers_list(_layers_obj, _viz_state.close_up);
  //     _deck_ist.setProps({ layers: layers_list });
  //   }
  // };

  // const rgn_callback = (event, _deck_ist, _layers_obj, _viz_state) => {
  //   const current = d3.select(event.currentTarget);
  //   const is_active = current.classed('active');

  //   if (is_active === false) {
  //     _viz_state.edit.visible = true;

  //     current.classed('active', _viz_state.edit.visible).style('color', 'blue');

  //     // hide alph button
  //     d3.select(_viz_state.edit.buttons.alph).style('display', 'none');

  //     // show sktch button
  //     d3.select(_viz_state.edit.buttons.sktch).style('display', 'inline-flex');
  //   } else {
  //     _viz_state.edit.visible = false;

  //     current.classed('active', _viz_state.edit.visible).style('color', 'gray');

  //     // show alph button
  //     d3.select(_viz_state.edit.buttons.alph).style('display', 'inline-flex');

  //     // show sktch button
  //     d3.select(_viz_state.edit.buttons.sktch).style('display', 'none');
  //   }

  //   update_edit_visitility(_layers_obj, _viz_state.edit.visible);
  //   const layers_list = get_layers_list(_layers_obj, _viz_state.close_up);
  //   _deck_ist.setProps({ layers: layers_list });

  //   _viz_state.edit.rgn_areas = _viz_state.edit.feature_collection.features.map(
  //     (feature, index) => ({
  //       name: (index + 1).toString(), // Assign numeric names starting from 1
  //       value: feature.properties.area, // Use the "area" property for the bar height
  //     })
  //   );

  //   _viz_state.edit.color_dict_rgn =
  //     _viz_state.edit.feature_collection.features.reduce(
  //       (acc, feature, index) => {
  //         acc[(index + 1).toString()] = feature.properties.color; // Use the "color" property
  //         return acc;
  //       },
  //       {}
  //     );

  // };

  const delete_polygon_index = (featureCollection, index) => {
    if (index >= 0 && index < featureCollection.features.length) {
      featureCollection.features.splice(index, 1);
    }
    return featureCollection;
  };

  const del_callback = (event, _deck_ist, _layers_obj, _viz_state) => {
    _viz_state.edit.feature_collection = delete_polygon_index(
      _viz_state.edit.feature_collection,
      _viz_state.edit.modify_index
    );

    _viz_state.edit.modify_index = null;

    // switch to view mode
    _layers_obj.edit_layer = _layers_obj.edit_layer.clone({
      id: 'edit-layer-delete',
      data: _viz_state.edit.feature_collection,
      mode: ViewMode,
      selectedFeatureIndexes: [],
    });

    const layers_list = get_layers_list(
      _layers_obj,
      _viz_state.close_up,
      _viz_state
    );
    _deck_ist.setProps({ layers: layers_list });

    // hide the DEL button
    d3.select(_viz_state.edit.buttons.del)
      .classed('active', false)
      .style('display', 'none');

    // show the NBHD and SKTCH buttons again
    d3.select(_viz_state.edit.buttons.nbhd).style('display', 'inline-flex');
    d3.select(_viz_state.edit.buttons.sktch).style('display', 'inline-flex');

    calc_and_update_rgn_bar_graph(_viz_state, _deck_ist, _layers_obj);
    sync_region_to_model(_viz_state);
  };

  // const bar_callback_nbhd = (_info) => {
  //   // console.log('clicking nbhd bar', _info)
  // };

  // const alph_callback = (event, _deck_ist, _layers_obj, _viz_state) => {
  //   // toggle color of the alpha txt button
  //   const _current = d3.select(event.currentTarget);

  //   if (_viz_state.nbhd.visible === true) {
  //     _viz_state.nbhd.visible = false;

  //     // hacky - need to store these buttons elsewhere
  //     d3.select(_viz_state.edit.buttons.alph).style('color', 'gray');

  //     // show rgn button
  //     d3.select(_viz_state.edit.buttons.rgn).style('display', 'inline-flex');

  //     _viz_state.sliders.alph.style.display = 'none';
  //   } else {
  //     _viz_state.nbhd.visible = true;
  //     d3.select(_viz_state.edit.buttons.alph).style('color', 'blue');

  //     // hide rgn button
  //     d3.select(_viz_state.edit.buttons.rgn).style('display', 'none');

  //     _viz_state.sliders.alph.style.display = 'block';
  //   }

  //   toggle_nbhd_layer_visibility(_layers_obj, _viz_state.nbhd.visible);

  //   // toggle with the opposite of _viz_state.nbhd.visible
  //   toggle_trx_layer_visibility(
  //     _layers_obj,
  //     _viz_state.nbhd.visible === true ? false : true
  //   );
  //   toggle_visibility_image_layers(
  //     _layers_obj,
  //     _viz_state.nbhd.visible === true ? false : true
  //   );
  //   toggle_background_layer_visibility(
  //     _layers_obj,
  //     _viz_state.nbhd.visible === true ? false : true
  //   );

  //   update_cell_pickable_state(
  //     _layers_obj,
  //     _viz_state.nbhd.visible === true ? false : true
  //   );
  //   update_path_pickable_state(
  //     _layers_obj,
  //     _viz_state.nbhd.visible === true ? false : true
  //   );

  //   const layers_list = get_layers_list(
  //     _layers_obj,
  //     _viz_state.close_up,
  //     _viz_state.nbhd.visible
  //   );
  //   _deck_ist.setProps({ layers: layers_list });

  //   _viz_state.nbhd.nbhd_areas =
  //     _viz_state.nbhd.feature_collection.features.map((feature, index) => ({
  //       name: (index + 1).toString(), // Assign numeric names starting from 1
  //       value: feature.properties.area, // Use the "area" property for the bar height
  //     }));
  // };

  if (viz_state.nbhd.is_nbhd) {
    viz_state.edit = viz_state.edit || {};
    viz_state.edit.buttons = {};
    viz_state.edit.mode = 'view';

    // Callback for NBHD button - toggles the edit layer visibility
    const nbhd_toggle_callback = (
      _event,
      _deck_ist,
      _layers_obj,
      _viz_state
    ) => {
      const visible = _viz_state.obs_store.viz_edit_layer.get();
      _viz_state.obs_store.viz_edit_layer.set(!visible);
    };

    const sketch_callback = (event, _deck_ist, _layers_obj, _viz_state) => {
      const current = d3.select(event.currentTarget);
      const is_active = current.classed('active');

      if (is_active === false) {
        current.classed('active', true).style('color', 'blue');

        _viz_state.edit.mode = 'sktch';

        update_edit_layer_mode(_layers_obj, DrawPolygonMode);
        update_cell_pickable_state(_layers_obj, false);
        update_path_pickable_state(_layers_obj, false);
        update_trx_pickable_state(_layers_obj, false);
      } else {
        _viz_state.edit.mode = 'view';

        current.classed('active', false).style('color', 'gray');

        update_edit_layer_mode(_layers_obj, ViewMode);
        update_cell_pickable_state(_layers_obj, true);
        update_path_pickable_state(_layers_obj, true);
        update_trx_pickable_state(_layers_obj, true);
      }

      const layers_list = get_layers_list(
        _layers_obj,
        _viz_state.close_up,
        _viz_state
      );
      _deck_ist.setProps({ layers: layers_list });
    };

    // Create NBHD button when nbhd_edit is true (replaces the old EDIT button)
    // This button toggles edit mode for neighborhoods
    if (viz_state.nbhd.edit) {
      make_edit_button(
        deck_ist,
        layers_obj,
        viz_state,
        nbhd_ctrl_container,
        'NBHD',
        40,
        nbhd_toggle_callback
      );
    }

    make_edit_button(
      deck_ist,
      layers_obj,
      viz_state,
      nbhd_ctrl_container,
      'SKTCH',
      40,
      sketch_callback
    );

    // SKTCH button is hidden initially, shown when NBHD edit mode is active
    d3.select(viz_state.edit.buttons.sktch).style('display', 'none');

    make_edit_button(
      deck_ist,
      layers_obj,
      viz_state,
      nbhd_ctrl_container,
      'DEL',
      30,
      del_callback
    );

    d3.select(viz_state.edit.buttons.del)
      .style('color', 'red')
      .style('display', 'none');

    // Set the nbhd button reference if it was created
    if (viz_state.edit.buttons.nbhd) {
      viz_state.buttons.buttons.nbhd = viz_state.edit.buttons.nbhd;
    }
  }

  if (viz_state.nbhd.is_nbhd) {
    viz_state.containers.bar_nbhd = make_bar_container();
    viz_state.containers.bar_nbhd.style.marginLeft = '0px';

    nbhd_container.appendChild(nbhd_ctrl_container);
    nbhd_container.appendChild(viz_state.containers.bar_nbhd);

    ctrl_container.appendChild(nbhd_container);

    make_bar_graph(
      viz_state.containers.bar_nbhd,
      bar_callback_nbhd,
      viz_state.nbhd.svg_bar_nbhd,
      viz_state.nbhd.bar_data,
      viz_state.nbhd.color_dict,
      deck_ist,
      layers_obj,
      viz_state
    );

    viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 0.2);
  }

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    // Plain black text, not a button -- there's no on/off toggle for the
    // slice bar graph the way CELL/TRX/NBHD toggle their layers.
    const slice_label_container = flex_container(
      'nbhd_cloud_slice_label_container',
      'row'
    );
    slice_label_container.style.marginLeft = '0px';
    slice_label_container.style.height = '22.5px';

    d3.select(slice_label_container)
      .append('div')
      .text('SLICE')
      .style('width', '40px')
      .style('text-align', 'left')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .style('color', 'black');

    nbhd_cloud_slice_container.appendChild(slice_label_container);
    nbhd_cloud_slice_container.appendChild(viz_state.containers.bar_slice);
    ctrl_container.appendChild(nbhd_cloud_slice_container);
  }

  if (hasGenes) {
    ctrl_container.appendChild(viz_state.genes.gene_search);
  }

  // === Add logo to top right === //
  // This render path is shared with the CellCloud/NeighborhoodCloud 3D-orbit
  // widgets (see celldega.js's render_landscape), so the docs link needs to
  // follow which one is actually showing rather than always pointing at
  // Landscape's page.
  const logoDocsPath = is_neighborhood_cloud_technology(technology)
    ? 'neighborhood-cloud'
    : is_orbit_technology(technology)
      ? 'cell-cloud'
      : 'landscape';
  ui_container.appendChild(make_logo_button(logoDocsPath));
  return ui_container;
};
