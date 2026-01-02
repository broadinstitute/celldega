import { ViewMode } from '@deck.gl-community/editable-layers';
import { AwsClient } from 'aws4fetch';
import * as d3 from 'd3';

import { calc_viewport } from '../deck-gl/core/calc_viewport';
import {
  ini_deck,
  set_deck_on_view_state_change,
  set_initial_view_state,
  set_get_tooltip,
  set_views_prop,
} from '../deck-gl/core/deck_ist';
import { set_views } from '../deck-gl/core/views';
import { ini_background_layer } from '../deck-gl/layers/background_layer';
import {
  ini_cell_layer,
  new_toggle_cell_layer_visibility,
  set_cell_layer_onclick,
  toggle_spatial_umap,
  update_cell_pickable_state,
} from '../deck-gl/layers/cell_layer';
import {
  ini_edit_layer,
  set_edit_layer_on_click,
  set_edit_layer_on_edit,
  update_edit_visitility,
  update_edit_layer_mode,
} from '../deck-gl/layers/edit_layer';
import { make_image_layers } from '../deck-gl/layers/image_layers';
import {
  ini_nbhd_layer,
  set_nbhd_layer_onclick,
  toggle_nbhd_layer_visibility,
} from '../deck-gl/layers/nbhd_layer';
import {
  ini_path_layer,
  set_path_layer_onclick,
  toggle_path_layer_visibility,
  update_path_pickable_state,
} from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  set_trx_layer_onclick,
  update_trx_layer_radius,
  toggle_trx_layer_visibility,
  update_trx_pickable_state,
} from '../deck-gl/layers/trx_layer';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import { ini_cache } from '../global_variables/cache';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { set_options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_dimensions } from '../global_variables/image_dimensions';
import {
  set_image_info,
  set_image_layer_colors,
  set_image_format,
} from '../global_variables/image_info';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_cluster_metadata } from '../global_variables/meta_cluster';
import { set_meta_gene } from '../global_variables/meta_gene';
import { update_selected_genes } from '../global_variables/selected_genes';
import { colorToRgba } from '../matrix/cat_data';
import { create_obs_store } from '../obs_store/obs_store';
import { initialize_nbhd_editor } from '../ui/nbhd_editor';
import { toggle_slider, set_image_layer_sliders } from '../ui/sliders';
import { get_img_layer_visible } from '../ui/text_buttons';
import { make_ist_ui_container } from '../ui/ui_containers';
import { refresh_layer } from '../utils/refresh_layer';
import { build_rotation_state } from '../utils/rotation';
import { create_scale_bar, PIXEL_SIZE_MICRONS } from '../utils/scale_bar';
import { update_cell_clusters } from '../widget_interactions/update_cell_clusters';
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm';

// Row group reading support
import { testRowGroupReading, getVersion as getParquetWasmVersion } from '../read_parquet/row_group_poc';
import { RowGroupTileReader } from '../read_parquet/row_group_tile_reader';

// Log parquet-wasm version on module load
console.log(`[landscape_ist] parquet-wasm version: ${getParquetWasmVersion()}`);

// Expose test function globally for browser console testing
// Usage: window.testRowGroupReading("https://example.com/row_grouped.parquet")
if (typeof window !== "undefined") {
  window.testRowGroupReading = testRowGroupReading;
}

/**
 * Initialize row group readers for tile data if the landscape uses row groups
 *
 * Uses formula-based row group indexing:
 *   row_group_index = tile_x * num_tiles_y + tile_y
 *
 * Only requires grid dimensions (num_tiles_x, num_tiles_y) from landscape_parameters.json
 *
 * @param {Object} viz_state - Visualization state
 * @param {string} base_url - Base URL for the landscape files
 * @returns {Promise<void>}
 */
async function initializeRowGroupReaders(viz_state, base_url) {
  const landscapeParams = viz_state.img.landscape_parameters;

  if (!landscapeParams.use_row_groups) {
    viz_state.use_row_groups = false;
    return;
  }

  console.log('[landscape_ist] Row group mode enabled, initializing readers...');

  const rowGroupFiles = landscapeParams.row_group_files || {};
  const tileGrid = landscapeParams.tile_grid || {};

  if (!tileGrid.num_tiles_x || !tileGrid.num_tiles_y) {
    console.error('[landscape_ist] Missing tile_grid dimensions in landscape_parameters');
    viz_state.use_row_groups = false;
    return;
  }

  const totalTiles = tileGrid.num_tiles_x * tileGrid.num_tiles_y;
  console.log(`[landscape_ist] Tile grid: ${tileGrid.num_tiles_x}x${tileGrid.num_tiles_y} = ${totalTiles} tiles`);
  console.log(`[landscape_ist] Using formula: row_group_index = tile_x * ${tileGrid.num_tiles_y} + tile_y`);

  viz_state.use_row_groups = true;
  viz_state.row_group_readers = {};
  viz_state.tile_grid = tileGrid;

  // Initialize transcript row group reader with grid dimensions
  if (rowGroupFiles.transcripts) {
    const trxUrl = `${base_url}/${rowGroupFiles.transcripts}`;
    console.log(`[landscape_ist] Initializing transcript reader from: ${trxUrl}`);

    viz_state.row_group_readers.trx = new RowGroupTileReader(trxUrl, tileGrid);
    await viz_state.row_group_readers.trx.initialize();

    const mode = viz_state.row_group_readers.trx.isStreaming() ? 'streaming (range requests)' : 'fallback (full fetch)';
    console.log(`[landscape_ist] Transcript reader ready - ${mode}`);
  }

  // Initialize cell segmentation row group reader with grid dimensions
  if (rowGroupFiles.cell_segmentation) {
    const cellUrl = `${base_url}/${rowGroupFiles.cell_segmentation}`;
    console.log(`[landscape_ist] Initializing cell reader from: ${cellUrl}`);

    viz_state.row_group_readers.cell = new RowGroupTileReader(cellUrl, tileGrid);
    await viz_state.row_group_readers.cell.initialize();

    const mode = viz_state.row_group_readers.cell.isStreaming() ? 'streaming (range requests)' : 'fallback (full fetch)';
    console.log(`[landscape_ist] Cell reader ready - ${mode}`);
  }

  console.log('[landscape_ist] Row group readers initialized successfully');
}

export const landscape_ist = async (
  el,
  ini_model,
  token,
  ini_x,
  ini_y,
  ini_z,
  ini_zoom,
  base_url,
  dataset_name = '',
  trx_radius = 0.25,
  width = 0,
  height = 800,
  meta_cell = {},
  meta_cell_attr = [],
  meta_cluster = {},
  meta_cluster_attr = [],
  umap = {},
  nbhd = {},
  nbhd_edit = false,
  landscape_state = 'spatial',
  segmentation = 'default',
  creds = {},
  view_change_custom_callback = null,
  rotation_orbit = 0,
  rotation_x = 0,
  rotate = 0,
  max_tiles_to_view = 50,
  scale_bar_microns_per_pixel = null,
  base_urls = [],
  cell_name_prefix = false
) => {
  if (width === 0) {
    width = '100%';
  }

  const viz_state = {};

  viz_state.obs_store = create_obs_store();

  viz_state.highlighted_cells = new Set();
  viz_state.selection_token = 0;

  const initial_selected_cells =
    typeof ini_model?.get === 'function'
      ? ini_model.get('selected_cells') || []
      : [];

  if (Array.isArray(initial_selected_cells)) {
    viz_state.highlighted_cells = new Set(initial_selected_cells);
    viz_state.obs_store.selected_cells.set(initial_selected_cells);
  }

  viz_state.max_tiles_to_view = max_tiles_to_view;

  // Set up centralized image visibility management via obs_store
  // This handles the logic for showing/hiding images based on gene/cluster selection and zoom level
  viz_state.update_viz_image_layers =
    viz_state.obs_store.setup_image_visibility_manager(get_img_layer_visible);

  viz_state.seg = {};
  viz_state.seg.version = segmentation;

  viz_state.root = el;
  viz_state.buttons = {};
  viz_state.buttons.blue = '#8797ff';
  viz_state.buttons.gray = 'gray';
  viz_state.buttons.light_gray = '#EEEEEE';
  viz_state.buttons.buttons = {};

  set_global_base_url(viz_state, base_url);

  // Store multi-dataset configuration
  viz_state.base_urls = base_urls;
  viz_state.cell_name_prefix = cell_name_prefix;

  viz_state.close_up = false;
  viz_state.model = ini_model;

  viz_state.nbhd = {};
  viz_state.nbhd.visible = false;
  viz_state.nbhd.edit = nbhd_edit;

  viz_state.spatial = {};

  // later we will parse the region from the s3 url

  if ('accessKeyId' in creds) {
    viz_state.aws = new AwsClient({
      accessKeyId: creds.accessKeyId,
      secretAccessKey: creds.secretAccessKey,
      sessionToken: creds.sessionToken,
      region: 'us-east-1',
      service: 's3',
    });

    // fetch after initialization of aws client is apparently required?
    const response = await viz_state.aws.fetch(
      `${base_url}/landscape_parameters.json`
    );

    if (!response.ok) {
      throw new Error(`Fetch failed: ${response.statusText}`);
    }

    // const json = await response.json();
    // el.textContent = "Fetch succeeded! Here's the object: " + JSON.stringify(json, null, 2).slice(0,50);
  } else {
    viz_state.aws = null;
  }

  // Set up neighborhood state - this block needs to run regardless of model type
  // to ensure is_nbhd is set correctly for the UI to create NBHD/SKTCH buttons
  if (Object.keys(nbhd).length === 0) {
    viz_state.nbhd.is_nbhd = nbhd_edit;

    viz_state.nbhd.ini_feature_collection = {
      type: 'FeatureCollection',
      features: [],
      inst_alpha: null,
    };

    viz_state.nbhd.feature_collection = viz_state.nbhd.ini_feature_collection;
  } else {
    viz_state.nbhd.is_nbhd = true;

    viz_state.nbhd.ini_feature_collection = nbhd;

    // find all unique categories in the nbhd features
    const unique_cats = new Set(
      nbhd.features.map((feature) => feature.properties.cat)
    );

    // calculate the area of all unique categories
    viz_state.nbhd.bar_data = Array.from(unique_cats)
      .map((cat) => {
        const features = nbhd.features.filter(
          (feature) => feature.properties.cat === cat
        );
        const area = features.reduce(
          (acc, feature) => acc + feature.properties.area,
          0
        );

        return {
          name: cat,
          value: area,
        };
      })
      .sort((a, b) => b.value - a.value);

    // parse colors from features and make a dictionary with cat name and
    // color as rgb array that is converted from hex
    viz_state.nbhd.color_dict = {};
    nbhd.features.forEach((feature) => {
      const color = colorToRgba(feature.properties.color);
      viz_state.nbhd.color_dict[feature.properties.cat] = color;
    });

    viz_state.nbhd.feature_collection = {
      type: 'FeatureCollection',
      features: nbhd.features,
    };
  }

  viz_state.containers = {};
  viz_state.containers.root_dim = {};
  viz_state.containers.root_dim.width = width;
  viz_state.containers.root_dim.height = height;

  viz_state.custom_callbacks = {};
  viz_state.custom_callbacks.view_change = view_change_custom_callback;

  viz_state.cats = {};
  viz_state.cats.cat = null;
  viz_state.cats.reset_cat = false;
  viz_state.cats.selected_cats = [];
  viz_state.cats.cell_cats = [];
  viz_state.cats.dict_cell_cats = {};
  viz_state.cats.color_dict_cluster = {};
  viz_state.cats.cluster_counts = [];
  viz_state.cats.polygon_cell_names = [];

  if (Object.keys(meta_cell).length === 0) {
    viz_state.cats.has_meta_cell = false;
  } else {
    viz_state.cats.has_meta_cell = true;
  }
  viz_state.cats.meta_cell = meta_cell;
  viz_state.cats.meta_cell_attr = meta_cell_attr;
  viz_state.cats.meta_cell_id_set = new Set(
    Object.keys(meta_cell || {}).map((cell_id) => String(cell_id))
  );
  viz_state.cats.inst_cell_attr = meta_cell_attr[0] || 'N.A.';

  if (Object.keys(meta_cluster).length === 0) {
    viz_state.cats.has_meta_cluster = false;
  } else {
    viz_state.cats.has_meta_cluster = true;
  }
  viz_state.cats.meta_cluster = meta_cluster;
  viz_state.cats.meta_cluster_attr = meta_cluster_attr;
  viz_state.cats.inst_cluster_attr = meta_cluster_attr[0] || 'N.A.';

  viz_state.umap = {};
  if (Object.keys(umap).length === 0) {
    viz_state.umap.has_umap = false;
  } else {
    viz_state.umap.has_umap = true;
  }
  viz_state.umap.umap = umap;

  const isUmapInit = landscape_state === 'umap';
  viz_state.obs_store.umap_state.set(isUmapInit);
  viz_state.obs_store.landscape_view.set(landscape_state);

  viz_state.genes = {};
  viz_state.genes.color_dict_gene = {};
  viz_state.genes.gene_names = [];
  viz_state.genes.meta_gene = {};
  viz_state.genes.gene_counts = [];
  viz_state.genes.selected_genes = [];
  viz_state.genes.trx_ini_radius = trx_radius;
  viz_state.genes.trx_names_array = [];
  viz_state.genes.trx_data = [];
  viz_state.genes.gene_text_box = '';
  viz_state.genes.trx_slider = document.createElement('input');
  viz_state.genes.gene_search = document.createElement('div');

  viz_state.cats.cell_exp_array = [];
  viz_state.cats.cell_names_array = [];
  viz_state.cats.cell_name_to_index_map = new Map();

  viz_state.img = {};
  viz_state.img.image_layer_colors = {};
  viz_state.img.image_layer_sliders = {};

  set_options(token);

  await set_landscape_parameters(viz_state.img, base_url, viz_state.aws);
  const tech = viz_state.img.landscape_parameters.technology;
  if (tech === 'Chromium' || tech === 'point-cloud') {
    viz_state.obs_store.viz_image_layers.set(false);
    viz_state.obs_store.viz_background_layer.set(false);
  }

  // Initialize row group readers if using row group storage mode
  await initializeRowGroupReaders(viz_state, base_url);

  const tmp_image_info = viz_state.img.landscape_parameters.image_info;

  // set image_name_for_dim using the first image info name
  const image_name_for_dim = tmp_image_info[0].name;

  viz_state.vector_name_integer =
    viz_state.img.landscape_parameters.use_int_index;

  set_image_format(
    viz_state.img,
    viz_state.img.landscape_parameters.image_format
  );
  set_image_info(viz_state.img, tmp_image_info);
  set_image_layer_sliders(viz_state.img);
  set_image_layer_colors(
    viz_state.img.image_layer_colors,
    viz_state.img.image_info
  );

  // Create and append the visualization.
  const root = document.createElement('div');
  root.style.position = 'relative';
  root.style.height = `${height}px`;
  root.style.border = '1px solid #d3d3d3';

  const userMicronsPerPixel =
    typeof scale_bar_microns_per_pixel === 'number' &&
    !Number.isNaN(scale_bar_microns_per_pixel) &&
    scale_bar_microns_per_pixel > 0
      ? scale_bar_microns_per_pixel
      : null;

  const defaultMicronsPerPixel = PIXEL_SIZE_MICRONS[tech];
  const micronsPerPixel = defaultMicronsPerPixel ?? userMicronsPerPixel;

  if (micronsPerPixel) {
    viz_state.scale_bar = create_scale_bar(micronsPerPixel, tech);
    root.appendChild(viz_state.scale_bar.container);
  }

  if (viz_state.scale_bar) {
    viz_state.obs_store.scale_bar_view_state.subscribe(
      (viewState) => {
        if (viewState && viz_state.scale_bar?.update) {
          viz_state.scale_bar.update(viewState);
        }
      },
      { immediate: false }
    );
  }

  if (tech === 'Chromium' || tech === 'point-cloud') {
    viz_state.dimensions = { width: 1, height: 1, tileSize: 1 };
  } else {
    await set_dimensions(viz_state, base_url, image_name_for_dim);
  }

  const centerX = viz_state.dimensions?.width
    ? viz_state.dimensions.width / 2
    : 0;
  const centerY = viz_state.dimensions?.height
    ? viz_state.dimensions.height / 2
    : 0;
  viz_state.rotation = build_rotation_state(rotate, [centerX, centerY]);

  await set_meta_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  await set_cluster_metadata(viz_state);

  viz_state.views = set_views(tech);

  const deck_ist = await ini_deck(root, width, height, tech);
  // set_initial_view_state(deck_ist, ini_x, ini_y, ini_z, ini_zoom)
  set_views_prop(deck_ist, viz_state.views);

  // initialize cell and trx caches
  viz_state.cache = {};
  viz_state.cache.cell = await ini_cache();
  // we will try to reuse cell functions to make trx cache
  viz_state.cache.trx = await ini_cache();

  viz_state.combo_data = {};

  viz_state.tooltip_cat_cell = '';

  set_get_tooltip(deck_ist, viz_state);

  viz_state.edit = {};
  viz_state.edit.svg_bar_rgn = d3.create('svg');
  viz_state.edit.rgn_areas = [];
  viz_state.edit.color_dict_rgn = {};
  // default opacity for editable neighborhoods
  viz_state.edit.rgn_opacity = 0.3;
  viz_state.edit.visible = false;
  viz_state.edit.modify_index = null;

  if (viz_state.model?.get) {
    if (Object.keys(viz_state.model.get('region')).length === 0) {
      viz_state.edit.feature_collection = {
        type: 'FeatureCollection',
        features: [],
      };
    } else {
      viz_state.edit.feature_collection = viz_state.model.get('region');
    }
  } else {
    viz_state.edit.feature_collection = {
      type: 'FeatureCollection',
      features: [],
    };
  }

  // When nbhd_edit is true and nbhd data is provided, initialize the edit layer
  // with the existing neighborhood features to allow editing pre-loaded neighborhoods
  if (nbhd_edit && Object.keys(nbhd).length > 0 && nbhd.features?.length > 0) {
    // Deep copy the nbhd features to the edit layer's feature collection
    // Colors are kept in hex format for consistency - the edit layer converts to RGB for rendering
    viz_state.edit.feature_collection = {
      type: 'FeatureCollection',
      features: nbhd.features.map((feature, index) => ({
        ...feature,
        properties: {
          ...feature.properties,
          // Keep color in hex format (the edit layer converts to RGB for rendering)
          color: feature.properties.color || '#808080',
          // Use existing name/cat or assign numeric index
          name: feature.properties.name || (index + 1).toString(),
          cat: feature.properties.cat || (index + 1).toString(),
        },
      })),
    };

    // Also update nbhd.bar_data and nbhd.color_dict for the bar graph
    // when editing pre-loaded neighborhoods
    const unique_cats = new Set(
      viz_state.edit.feature_collection.features.map((f) => f.properties.cat)
    );
    viz_state.nbhd.bar_data = Array.from(unique_cats)
      .map((cat) => {
        const features = viz_state.edit.feature_collection.features.filter(
          (f) => f.properties.cat === cat
        );
        const area = features.reduce(
          (acc, f) => acc + (f.properties.area || 0),
          0
        );
        return { name: cat, value: area };
      })
      .sort((a, b) => b.value - a.value);

    viz_state.nbhd.color_dict = {};
    viz_state.edit.feature_collection.features.forEach((feature) => {
      const { color } = feature.properties;
      // Convert hex to RGBA for the color dict used in bar graphs
      viz_state.nbhd.color_dict[feature.properties.cat] = colorToRgba(color);
    });
  }

  const background_layer = ini_background_layer(viz_state);
  const image_layers = await make_image_layers(viz_state);
  const cell_layer = await ini_cell_layer(base_url, viz_state);
  const path_layer = await ini_path_layer(viz_state);
  const trx_layer = ini_trx_layer(viz_state);
  const edit_layer = ini_edit_layer(viz_state);
  const nbhd_layer = ini_nbhd_layer(viz_state, true);

  // make layers object
  const layers_obj = {
    background_layer,
    image_layers,
    cell_layer,
    path_layer,
    trx_layer,
    nbhd_layer,
    edit_layer,
  };

  const refresh_cell_layer = () => {
    const selected_cats_name = viz_state.cats.selected_cats.join('-');

    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-${selected_cats_name}-sel-${viz_state.selection_token}`,
      updateTriggers: {
        ...layers_obj.cell_layer.props.updateTriggers,
        getPosition: [viz_state.obs_store.umap_state.get()],
        getFillColor: [viz_state.selection_token],
      },
    });

    // Toggle cell layer readiness so deck.gl re-renders when selections arrive
    // from the Python backend.
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: false,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: true,
    });
  };

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    nbhd_layer: true,
    edit_layer: true,
  });

  viz_state.obs_store.selected_nbhds.subscribe(
    (selected_nbhds) => {
      const selected_nbhds_name = selected_nbhds.join('-');

      layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        id: `nbhd-layer-${selected_nbhds_name}`,
      });
    },
    { immediate: false }
  );

  viz_state.obs_store.viz_nbhd_layer.subscribe(
    (visible) => {
      if (visible) {
        // set cell layer to not visible
        new_toggle_cell_layer_visibility(viz_state.layers_obj, false);

        // set gene/cat bars to disabled color
        viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 0.2);
        viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 0.2);
        viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);

        viz_state.buttons.buttons.cell.style('color', 'gray');
        viz_state.buttons.buttons.trx.style('color', 'gray');
        viz_state.buttons.buttons.nbhd?.style('color', 'blue');

        toggle_slider(viz_state.sliders.cell, false);
        toggle_slider(viz_state.sliders.trx, false);
        if (viz_state.nbhd.is_nbhd) {
          toggle_slider(viz_state.sliders.nbhd, true);
        }
      } else {
        new_toggle_cell_layer_visibility(viz_state.layers_obj, true);

        viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);
        viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 1.0);
        viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 0.2);

        viz_state.buttons.buttons.cell.style('color', 'blue');
        viz_state.buttons.buttons.trx.style('color', 'blue');
        viz_state.buttons.buttons.nbhd?.style('color', 'gray');

        toggle_slider(viz_state.sliders.cell, true);
        toggle_slider(viz_state.sliders.trx, true);
        if (viz_state.nbhd.is_nbhd) {
          toggle_slider(viz_state.sliders.nbhd, false);
        }
      }
      if (visible) {
        viz_state.obs_store.viz_edit_layer.set(false);
      }
    },
    { immediate: false }
  );

  // set onclicks after all layers are made
  set_cell_layer_onclick(deck_ist, layers_obj, viz_state);
  set_path_layer_onclick(deck_ist, layers_obj, viz_state);
  set_trx_layer_onclick(deck_ist, layers_obj, viz_state);
  set_edit_layer_on_edit(deck_ist, layers_obj, viz_state);
  set_edit_layer_on_click(deck_ist, layers_obj, viz_state);
  set_nbhd_layer_onclick(deck_ist, layers_obj, viz_state);

  viz_state.obs_store.deck_ready.subscribe((ready) => {
    if (ready) {
      const list = get_layers_list(viz_state.layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: list });
    }
  });

  viz_state.obs_store.viz_edit_layer.subscribe(
    (visible) => {
      update_edit_visitility(layers_obj, visible);
      if (visible) {
        viz_state.obs_store.viz_nbhd_layer.set(false);
        toggle_nbhd_layer_visibility(layers_obj, false);
        toggle_trx_layer_visibility(layers_obj, false);
        viz_state.buttons.buttons.trx.style('color', 'gray');
        d3.select(viz_state.edit.buttons.nbhd).style('color', 'blue');
        d3.select(viz_state.edit.buttons.sktch)
          .style('display', 'inline-flex')
          .style('color', 'gray')
          .classed('active', false);
        if (viz_state.nbhd.edit && viz_state.containers.nbhd_opacity_slider) {
          d3.select(viz_state.containers.nbhd_opacity_slider).style(
            'display',
            'inline-flex'
          );
          toggle_slider(viz_state.sliders.nbhd_opacity, true);
        }
      } else {
        toggle_trx_layer_visibility(layers_obj, true);
        viz_state.buttons.buttons.trx.style('color', 'blue');
        d3.select(viz_state.edit.buttons.nbhd)
          .style('color', 'gray')
          .classed('active', false);
        d3.select(viz_state.edit.buttons.sktch)
          .style('display', 'none')
          .style('color', 'gray')
          .classed('active', false);
        update_edit_layer_mode(layers_obj, ViewMode);
        update_cell_pickable_state(layers_obj, true);
        update_path_pickable_state(layers_obj, true);
        update_trx_pickable_state(layers_obj, true);
        if (viz_state.nbhd.edit && viz_state.containers.nbhd_opacity_slider) {
          d3.select(viz_state.containers.nbhd_opacity_slider).style(
            'display',
            'none'
          );
          toggle_slider(viz_state.sliders.nbhd_opacity, false);
        }
      }
      refresh_layer(viz_state, layers_obj, 'edit_layer');
    },
    { immediate: false }
  );

  viz_state.obs_store.selected_cats.subscribe((selected_cats) => {
    const selected_cats_name = selected_cats.join('-');

    refresh_cell_layer();

    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-${selected_cats_name}`,
    });
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      path_layer: true,
    });
  });

  viz_state.obs_store.selected_cells.subscribe((selected_cells) => {
    viz_state.highlighted_cells = new Set(selected_cells ?? []);
    viz_state.selection_token += 1;
    refresh_cell_layer();
  });

  viz_state.obs_store.selected_genes.subscribe((selected_genes) => {
    const selected_genes_name = selected_genes.join('-');
    layers_obj.trx_layer = layers_obj.trx_layer.clone({
      id: `trx-layer-${selected_genes_name}`,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      trx_layer: true,
    });
  });

  update_trx_layer_radius(layers_obj, trx_radius);

  if (viz_state.obs_store.umap_state.get() === true) {
    viz_state.obs_store.viz_background_layer.set(false);
    viz_state.obs_store.viz_image_layers.set(false);

    toggle_trx_layer_visibility(layers_obj, false);
    toggle_path_layer_visibility(layers_obj, false);
  }

  set_initial_view_state(
    deck_ist,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    viz_state,
    rotation_orbit,
    rotation_x
  );

  set_deck_on_view_state_change(deck_ist, layers_obj, viz_state);

  if (viz_state.model?.on) {
    viz_state.model.on('change:update_trigger', () =>
      update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state)
    );
    viz_state.model.on('change:cell_clusters', () =>
      update_cell_clusters(deck_ist, layers_obj, viz_state)
    );
    viz_state.model.on('change:selected_cells', () => {
      const cells = viz_state.model.get('selected_cells') || [];
      viz_state.obs_store.selected_cells.set(cells);
    });
  }

  const ui_container = make_ist_ui_container(
    dataset_name,
    deck_ist,
    layers_obj,
    viz_state
  );

  // UI and Viz Container
  el.appendChild(ui_container);
  el.appendChild(root);

  // Initialize neighborhood editor dialog if nbhd_edit mode is enabled
  if (viz_state.nbhd.edit) {
    viz_state.nbhd_editor = initialize_nbhd_editor(
      viz_state,
      deck_ist,
      layers_obj
    );
  }

  const isChromium = ['Chromium', 'point-cloud'].includes(
    viz_state.img.landscape_parameters.technology
  );
  viz_state.obs_store.landscape_view.subscribe(
    (view) => {
      const isUmap = view === 'umap';
      viz_state.obs_store.umap_state.set(isUmap);

      if (viz_state.scale_bar) {
        viz_state.scale_bar.setVisible(!isUmap);
      }

      toggle_spatial_umap(deck_ist, layers_obj, viz_state);

      if (isUmap) {
        viz_state.buttons.buttons.umap.style('color', 'blue');
        if (!isChromium) {
          viz_state.buttons.buttons.spatial.style('color', 'gray');
          viz_state.buttons.buttons.img.style('color', 'gray');
        }

        viz_state.obs_store.viz_background_layer.set(false);
        viz_state.obs_store.viz_image_layers.set(false);

        toggle_trx_layer_visibility(layers_obj, false);
        toggle_path_layer_visibility(layers_obj, false);

        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: false,
          path_layer: false,
          trx_layer: false,
        });

        viz_state.layers_obj = layers_obj;

        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: true,
          path_layer: true,
          trx_layer: true,
        });
      } else {
        if (!isChromium) {
          viz_state.buttons.buttons.umap.style('color', 'gray');
          viz_state.buttons.buttons.spatial.style('color', 'blue');
          viz_state.buttons.buttons.img.style('color', 'blue');
        }

        toggle_trx_layer_visibility(layers_obj, true);
        toggle_path_layer_visibility(layers_obj, true);

        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: false,
          path_layer: false,
          trx_layer: false,
        });
        viz_state.layers_obj = layers_obj;
        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: true,
          path_layer: true,
          trx_layer: true,
        });

        setTimeout(() => {
          viz_state.obs_store.viz_background_layer.set(true);
          viz_state.obs_store.viz_image_layers.set(true);
        }, 3000);
      }
    },
    { immediate: false }
  );

  // Callback registries for external listeners
  const callbacks = {
    on_gene_select: [],
    on_cluster_select: [],
    on_clusters_select: [],
  };

  const landscape = {
    /**
     * Register a callback for gene selection events.
     * @param {function} callback - Function called with (gene_name)
     */
    on_gene_select: (callback) => {
      callbacks.on_gene_select.push(callback);
    },
    /**
     * Register a callback for single cluster selection events.
     * @param {function} callback - Function called with (cluster_id)
     */
    on_cluster_select: (callback) => {
      callbacks.on_cluster_select.push(callback);
    },
    /**
     * Register a callback for multiple cluster selection (via dendrogram).
     * @param {function} callback - Function called with (cluster_ids_array)
     */
    on_clusters_select: (callback) => {
      callbacks.on_clusters_select.push(callback);
    },
    update_matrix_gene: async (inst_gene) => {
      const reset_gene = inst_gene === viz_state.cats.cat;
      const new_cat = reset_gene ? 'cluster' : inst_gene;

      update_cat(viz_state.cats, new_cat);
      update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
      update_selected_cats(
        viz_state.cats,
        new_cat === 'cluster' ? [] : [inst_gene],
        viz_state.obs_store
      );
      await update_cell_exp_array(
        viz_state.cats,
        viz_state.genes,
        viz_state.global_base_url,
        inst_gene,
        viz_state.seg.version,
        viz_state.vector_name_integer,
        viz_state.aws
      );

      viz_state.layers_obj = layers_obj;

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: true,
      });

      // Notify listeners
      callbacks.on_gene_select.forEach((cb) => cb(inst_gene));
    },
    update_matrix_col: async (inst_col) => {
      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, [inst_col], viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: false,
        path_layer: false,
        trx_layer: false,
      });
      viz_state.layers_obj = layers_obj;

      // Notify listeners
      callbacks.on_cluster_select.forEach((cb) => cb(inst_col));
    },
    update_matrix_dendro_col: async (selected_cols) => {
      // const inst_gene = 'cluster'
      const new_cats = selected_cols; // click_info.value.selected_names

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);

      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: false,
        path_layer: false,
        trx_layer: false,
      });
      viz_state.layers_obj = layers_obj;

      // Notify listeners
      callbacks.on_clusters_select.forEach((cb) => cb(selected_cols));
    },
    update_view_state: async (new_view_state, close_up, _trx_layer) => {
      viz_state.close_up = close_up;

      calc_viewport(
        new_view_state,
        deck_ist,
        layers_obj,
        viz_state,
        viz_state.obs_store
      );
      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: false,
        path_layer: false,
        trx_layer: false,
      });

      deck_ist.setProps({
        controller: { doubleClickZoom: false },
        initialViewState: new_view_state,
        views: viz_state.views,
      });

      viz_state.layers_obj = layers_obj;
    },
    update_layers: () => {},
    finalize: () => {
      deck_ist.finalize();
    },
  };

  return landscape;
};
