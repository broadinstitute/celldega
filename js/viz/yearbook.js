import * as d3 from 'd3';
import { AwsClient } from 'aws4fetch';

import { calc_viewport } from '../deck-gl/core/calc_viewport';
import {
  ini_deck,
  set_deck_on_view_state_change,
  set_get_tooltip,
  set_views_prop,
} from '../deck-gl/core/deck_ist';
import { ini_background_layer } from '../deck-gl/layers/background_layer';
import {
  ini_cell_layer,
  new_toggle_cell_layer_visibility,
  set_cell_layer_onclick,
  update_cell_pickable_state,
} from '../deck-gl/layers/cell_layer';
import { make_image_layers, make_yearbook_image_layers } from '../deck-gl/layers/image_layers';
import {
  ini_path_layer,
  set_path_layer_onclick,
  toggle_path_layer_visibility,
  update_path_pickable_state,
  update_path_layer_data,
} from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  set_trx_layer_onclick,
  update_trx_layer_radius,
  toggle_trx_layer_visibility,
  update_trx_pickable_state,
  update_trx_layer_data,
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
import { create_obs_store } from '../obs_store/obs_store';
import { set_image_layer_sliders } from '../ui/sliders';
import { visibleTiles } from '../vector_tile/visibleTiles';

import { make_yearbook_ui_container } from '../ui/yearbook_ui';
import {
  calc_portrait_viewports,
  create_yearbook_views,
  get_discontiguous_tiles,
} from '../deck-gl/core/yearbook_viewports';

const PIXEL_SIZE_MICRONS = {
  Xenium: 0.2125,
  MERSCOPE: 0.108,
};

const create_scale_bar = (micronsPerPixel, tech) => {
  const techKey = tech || '';
  const blackLabelTechs = ['Visium-HD'];
  const whiteLabelTechs = ['Xenium', 'MERSCOPE'];

  const labelColor = blackLabelTechs.includes(techKey)
    ? 'black'
    : whiteLabelTechs.includes(techKey)
      ? 'white'
      : 'white';

  const rev_labelColor = labelColor === 'white' ? 'black' : 'white';

  const container = document.createElement('div');
  container.style.position = 'absolute';
  container.style.bottom = '10px';
  container.style.left = '10px';
  container.style.backgroundColor = 'transparent';
  container.style.color = labelColor;
  container.style.padding = '6px 8px';
  container.style.fontSize = '12px';
  container.style.lineHeight = '1.2';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'flex-start';
  container.style.pointerEvents = 'none';
  container.style.zIndex = '10';
  container.style.opacity = '0.5';

  const label = document.createElement('div');
  label.textContent = '1 µm';

  const bar = document.createElement('div');
  bar.style.height = '2px';
  bar.style.backgroundColor = labelColor;
  bar.style.outline = `1px solid ${rev_labelColor}`;
  bar.style.marginTop = '4px';
  bar.style.width = '80px';

  if (labelColor === 'white') {
    container.style.textShadow = '0 0 3px black';
  }

  container.appendChild(label);
  container.appendChild(bar);

  const formatLabel = (microns) => {
    if (microns >= 1000) {
      const millimeters = microns / 1000;
      if (millimeters >= 10) {
        return `${Math.round(millimeters)} mm`;
      }
      if (millimeters >= 1) {
        return `${Number(millimeters.toFixed(1))} mm`;
      }
    }

    if (microns >= 100) {
      return `${Math.round(microns)} µm`;
    }
    if (microns >= 10) {
      return `${Number(microns.toFixed(1))} µm`;
    }
    return `${Number(microns.toPrecision(2))} µm`;
  };

  const setVisible = (visible) => {
    container.style.display = visible ? 'flex' : 'none';
  };

  const update = ({ zoom }) => {
    const zoomFactor = Math.pow(2, zoom || 0);
    const micronsPerScreenPixel = micronsPerPixel / zoomFactor;
    const targetPixelWidth = 100;
    const rawMicrons = micronsPerScreenPixel * targetPixelWidth;
    const cappedMicrons = Math.min(rawMicrons, 1000);

    const magnitude = Math.pow(10, Math.floor(Math.log10(cappedMicrons)));
    const normalized = cappedMicrons / magnitude;

    let niceNormalized = 1;
    if (normalized > 5) {
      niceNormalized = 10;
    } else if (normalized > 2) {
      niceNormalized = 5;
    } else if (normalized > 1) {
      niceNormalized = 2;
    }

    const barMicrons = niceNormalized * magnitude;
    const barPixelWidth = barMicrons / micronsPerScreenPixel;

    label.textContent = formatLabel(barMicrons);
    bar.style.width = `${barPixelWidth}px`;
  };

  return { container, update, setVisible };
};

/**
 * Calculate initial zoom level based on portrait size in micrometers
 */
const calc_initial_zoom = (portrait_size_um, portrait_pixel_size, micronsPerPixel) => {
  // portrait_size_um is the size in micrometers we want to see
  // portrait_pixel_size is the actual pixel size of the portrait on screen
  // micronsPerPixel is the base resolution of the image

  // Calculate how many image pixels correspond to portrait_size_um
  const image_pixels_for_portrait = portrait_size_um / micronsPerPixel;

  // Calculate zoom level to fit this many image pixels into portrait_pixel_size screen pixels
  const zoom = Math.log2(portrait_pixel_size / image_pixels_for_portrait);

  return zoom;
};

export const yearbook = async (
  el,
  ini_model,
  token,
  base_url,
  dataset_name = '',
  cells = [],
  num_rows = 2,
  num_cols = 3,
  portrait_size_um = 50,
  portrait_gap = 4,
  width = 0,
  height = 800,
  meta_cell = {},
  meta_cell_attr = [],
  meta_cluster = {},
  meta_cluster_attr = [],
  segmentation = 'default',
  creds = {},
  scale_bar_microns_per_pixel = null,
  current_page = 0
) => {
  if (width === 0) {
    width = '100%';
  }

  const viz_state = {};

  viz_state.obs_store = create_obs_store();
  viz_state.highlighted_cells = new Set();
  viz_state.selection_token = 0;

  // Yearbook-specific state
  viz_state.yearbook = {
    cells: cells,
    num_rows: num_rows,
    num_cols: num_cols,
    portrait_size_um: portrait_size_um,
    portrait_gap: portrait_gap,
    current_page: current_page,
    zoom_level: 0,
    portrait_centers: [], // Will store the center coordinates for each portrait
  };

  viz_state.max_tiles_to_view = 50;
  viz_state.seg = {};
  viz_state.seg.version = segmentation;

  viz_state.root = el;
  viz_state.buttons = {};
  viz_state.buttons.blue = '#8797ff';
  viz_state.buttons.gray = 'gray';
  viz_state.buttons.light_gray = '#EEEEEE';
  viz_state.buttons.buttons = {};

  set_global_base_url(viz_state, base_url);

  viz_state.close_up = true; // Always in close-up mode for yearbook
  viz_state.model = ini_model;

  viz_state.containers = {};
  viz_state.containers.root_dim = {};
  viz_state.containers.root_dim.width = width;
  viz_state.containers.root_dim.height = height;

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

  viz_state.genes = {};
  viz_state.genes.color_dict_gene = {};
  viz_state.genes.gene_names = [];
  viz_state.genes.meta_gene = {};
  viz_state.genes.gene_counts = [];
  viz_state.genes.selected_genes = [];
  viz_state.genes.trx_ini_radius = 0.25;
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

  // Yearbook doesn't support UMAP view
  viz_state.umap = {};
  viz_state.umap.has_umap = false;
  viz_state.umap.umap = {};

  // Yearbook doesn't support neighborhood editing
  viz_state.nbhd = {};
  viz_state.nbhd.visible = false;
  viz_state.nbhd.edit = false;
  viz_state.nbhd.is_nbhd = false;
  viz_state.nbhd.feature_collection = { type: 'FeatureCollection', features: [] };

  viz_state.spatial = {};

  // Set up AWS credentials if provided
  if ('accessKeyId' in creds) {
    viz_state.aws = new AwsClient({
      accessKeyId: creds.accessKeyId,
      secretAccessKey: creds.secretAccessKey,
      sessionToken: creds.sessionToken,
    });
  } else {
    viz_state.aws = null;
  }

  // Initialize rotation state (no rotation for yearbook)
  viz_state.rotation = { hasRotation: false };

  set_options(token);

  await set_landscape_parameters(viz_state.img, base_url, viz_state.aws);
  const tech = viz_state.img.landscape_parameters.technology;

  const tmp_image_info = viz_state.img.landscape_parameters.image_info;
  const image_name_for_dim = tmp_image_info[0].name;

  viz_state.vector_name_integer = viz_state.img.landscape_parameters.use_int_index;

  set_image_format(viz_state.img, viz_state.img.landscape_parameters.image_format);
  set_image_info(viz_state.img, tmp_image_info);
  set_image_layer_sliders(viz_state.img);
  set_image_layer_colors(viz_state.img.image_layer_colors, viz_state.img.image_info);

  // Create and append the visualization
  const root = document.createElement('div');
  root.style.position = 'relative';
  root.style.height = `${height}px`;
  root.style.border = '1px solid #d3d3d3';

  // Calculate microns per pixel for scale bar
  const userMicronsPerPixel =
    typeof scale_bar_microns_per_pixel === 'number' &&
    !Number.isNaN(scale_bar_microns_per_pixel) &&
    scale_bar_microns_per_pixel > 0
      ? scale_bar_microns_per_pixel
      : null;

  const defaultMicronsPerPixel = PIXEL_SIZE_MICRONS[tech];
  const micronsPerPixel = defaultMicronsPerPixel ?? userMicronsPerPixel;
  viz_state.yearbook.micronsPerPixel = micronsPerPixel;

  if (micronsPerPixel) {
    viz_state.scale_bar = create_scale_bar(micronsPerPixel, tech);
    root.appendChild(viz_state.scale_bar.container);
  }

  await set_dimensions(viz_state, base_url, image_name_for_dim);

  await set_meta_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  await set_cluster_metadata(viz_state);

  // Initialize cell and trx caches
  viz_state.cache = {};
  viz_state.cache.cell = await ini_cache();
  viz_state.cache.trx = await ini_cache();

  viz_state.combo_data = {};
  viz_state.combo_data.trx = [];
  viz_state.combo_data.cell = [];
  viz_state.tooltip_cat_cell = '';

  // Edit state (not used in yearbook but needed for layer compatibility)
  viz_state.edit = {};
  viz_state.edit.feature_collection = { type: 'FeatureCollection', features: [] };
  viz_state.edit.visible = false;

  // Calculate portrait dimensions FIRST (needed for image layer setup)
  const actual_width = typeof width === 'string' ? el.clientWidth || 1000 : width;
  const available_width = actual_width - (num_cols - 1) * portrait_gap;
  const available_height = height - 100 - (num_rows - 1) * portrait_gap; // 100 for control panel
  const portrait_pixel_width = available_width / num_cols;
  const portrait_pixel_height = available_height / num_rows;
  const portrait_pixel_size = Math.min(portrait_pixel_width, portrait_pixel_height);

  viz_state.yearbook.portrait_pixel_size = portrait_pixel_size;

  // Calculate initial zoom based on portrait_size_um
  // Also calculate portrait size in image/data coordinates for tile loading
  if (micronsPerPixel) {
    const initial_zoom = calc_initial_zoom(
      portrait_size_um,
      portrait_pixel_size,
      micronsPerPixel
    );
    viz_state.yearbook.zoom_level = initial_zoom;

    // Portrait size in image pixels (data coordinates)
    // This is how many image pixels the portrait_size_um covers
    viz_state.yearbook.portrait_data_size = portrait_size_um / micronsPerPixel;
  } else {
    // Fallback: assume 0.2 microns per pixel (Xenium default)
    viz_state.yearbook.portrait_data_size = portrait_size_um / 0.2125;
  }

  // Initialize base layers (image layers will be created per-portrait later)
  const background_layer = ini_background_layer(viz_state);
  let image_layers = []; // Will be populated with per-portrait layers
  const cell_layer = await ini_cell_layer(base_url, viz_state);
  const path_layer = await ini_path_layer(viz_state);
  const trx_layer = ini_trx_layer(viz_state);

  // Create deck instance with multiple views
  const views = create_yearbook_views(num_rows, num_cols, portrait_pixel_size, portrait_gap);
  viz_state.views = views;

  const deck_yearbook = await ini_deck(root, actual_width, height - 100, tech);
  set_views_prop(deck_yearbook, views);
  set_get_tooltip(deck_yearbook, viz_state);

  // Set up layer filter to render per-portrait image layers only in their target viewport
  // Image layer IDs are like "yb-DAPI-p0-page0" where p0 means portrait 0
  // Viewport IDs are like "portrait-0"
  deck_yearbook.setProps({
    layerFilter: ({ layer, viewport }) => {
      const layerId = layer.id;
      // Check if this is a per-portrait image layer (contains -pN- pattern)
      const portraitMatch = layerId.match(/-p(\d+)-/);
      if (portraitMatch) {
        const portraitIndex = parseInt(portraitMatch[1], 10);
        const targetViewportId = `portrait-${portraitIndex}`;
        return viewport.id === targetViewportId;
      }
      // All other layers (vector, background) render in all viewports
      return true;
    },
  });

  // Make layers object (nbhd_layer and edit_layer are null for yearbook)
  const layers_obj = {
    background_layer,
    image_layers,
    cell_layer,
    path_layer,
    trx_layer,
    nbhd_layer: null,
    edit_layer: null,
  };

  viz_state.layers_obj = layers_obj;

  // Calculate portrait centers based on cell positions
  const update_portrait_centers = async () => {
    const portraits_per_page = num_rows * num_cols;
    // Use viz_state values which get updated by pagination/model changes
    const inst_current_page = viz_state.yearbook.current_page;
    const inst_cells = viz_state.yearbook.cells;
    const start_index = inst_current_page * portraits_per_page;
    const page_cells = inst_cells.slice(start_index, start_index + portraits_per_page);

    console.log(`Yearbook: Page ${inst_current_page + 1}, showing cells ${start_index} to ${start_index + page_cells.length}`);

    // Get cell positions from the scatter data
    const centers = page_cells.map((cell_id) => {
      const cell_index = viz_state.cats.cell_name_to_index_map.get(cell_id);
      if (cell_index !== undefined && viz_state.spatial.cell_scatter_data_objects) {
        const cell_data = viz_state.spatial.cell_scatter_data_objects[cell_index];
        if (cell_data && cell_data.position) {
          return {
            cell_id,
            x: cell_data.position[0],
            y: cell_data.position[1],
          };
        }
      }
      // Fallback to center of image if cell not found
      console.warn(`Yearbook: Cell ${cell_id} not found in scatter data`);
      return {
        cell_id,
        x: viz_state.dimensions.width / 2,
        y: viz_state.dimensions.height / 2,
      };
    });

    viz_state.yearbook.portrait_centers = centers;
    return centers;
  };

  // Update initial view states for all portraits
  const update_all_portraits = async () => {
    const centers = await update_portrait_centers();
    const { zoom_level, portrait_data_size } = viz_state.yearbook;
    const { tile_size } = viz_state.img.landscape_parameters;

    // Use portrait_data_size (in image pixels) for tile calculation
    // This ensures we only load tiles that cover the actual visible area
    const all_tiles = get_discontiguous_tiles(
      centers,
      0, // zoom=0 since we're using data coordinates directly
      portrait_data_size,
      portrait_data_size,
      tile_size
    );

    console.log(`Yearbook: Loading ${all_tiles.length} tiles for ${centers.length} portraits (${portrait_data_size.toFixed(0)} px per portrait)`);

    // Update transcript and path layers with combined tile data
    await update_trx_layer_data(base_url, all_tiles, layers_obj, viz_state);
    await update_path_layer_data(base_url, all_tiles, layers_obj, viz_state);

    // Create image layers that cover all portrait regions
    // Use page number in cache key so layers refresh on pagination
    const page_cache_key = `page${viz_state.yearbook.current_page}`;
    layers_obj.image_layers = await make_yearbook_image_layers(
      viz_state,
      centers,
      portrait_data_size,
      page_cache_key
    );
    viz_state.layers_obj = layers_obj;

    // Create view states for each portrait and update viewStatesRef
    const view_states = {};
    centers.forEach((center, index) => {
      const view_id = `portrait-${index}`;
      view_states[view_id] = {
        target: [center.x, center.y, 0],
        zoom: zoom_level,
      };
      // Also update viewStatesRef for zoom sync
      viewStatesRef[view_id] = view_states[view_id];
    });

    // Force deck to update with new view states and layers
    // Use a unique timestamp to force layer recreation
    const timestamp = Date.now();
    
    // Clone layers with new IDs to force refresh
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-page-${viz_state.yearbook.current_page}-${timestamp}`,
    });
    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-page-${viz_state.yearbook.current_page}-${timestamp}`,
    });
    layers_obj.trx_layer = layers_obj.trx_layer.clone({
      id: `trx-layer-page-${viz_state.yearbook.current_page}-${timestamp}`,
    });

    // Get the updated layers list (filter out null layers for yearbook)
    const layers_list = get_layers_list(layers_obj, viz_state.close_up).filter(l => l !== null);

    // Apply all changes at once
    deck_yearbook.setProps({
      initialViewState: view_states,
      layers: layers_list,
    });

    // Update bar graphs based on visible data
    update_bar_graphs(viz_state);

    // Update scale bar
    if (viz_state.scale_bar) {
      viz_state.scale_bar.update({ zoom: zoom_level });
    }
  };

  // Update bar graphs based on data in all visible portraits
  const update_bar_graphs = (viz_state) => {
    const centers = viz_state.yearbook.portrait_centers;
    const portrait_data_size = viz_state.yearbook.portrait_data_size;
    // Use half the portrait data size as the radius for filtering
    const half_view_size = portrait_data_size / 2;

    // Filter transcripts visible in any portrait
    const filtered_transcripts = (viz_state.combo_data.trx || []).filter((pos) => {
      return centers.some((center) => {
        return (
          pos.x >= center.x - half_view_size &&
          pos.x <= center.x + half_view_size &&
          pos.y >= center.y - half_view_size &&
          pos.y <= center.y + half_view_size
        );
      });
    });

    const filtered_gene_names = filtered_transcripts.map((t) => t.name);

    const new_bar_data = filtered_gene_names
      .reduce((acc, gene) => {
        const existingGene = acc.find((item) => item.name === gene);
        if (existingGene) {
          existingGene.value += 1;
        } else {
          acc.push({ name: gene, value: 1 });
        }
        return acc;
      }, [])
      .filter((item) => item.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 100);

    viz_state.obs_store.new_gene_bar_data.set(new_bar_data);

    // Filter cells visible in any portrait
    const filtered_cells = (viz_state.combo_data.cell || []).filter((pos) => {
      return centers.some((center) => {
        return (
          pos.x >= center.x - half_view_size &&
          pos.x <= center.x + half_view_size &&
          pos.y >= center.y - half_view_size &&
          pos.y <= center.y + half_view_size
        );
      });
    });

    const filtered_cell_cats = filtered_cells.map((cell) => cell.cat);

    const new_bar_data_cell = filtered_cell_cats
      .reduce((acc, cat) => {
        const existing_cat = acc.find((item) => item.name === cat);
        if (existing_cat) {
          existing_cat.value += 1;
        } else {
          acc.push({ name: cat, value: 1 });
        }
        return acc;
      }, [])
      .filter((item) => item.value > 0)
      .sort((a, b) => b.value - a.value);

    viz_state.obs_store.new_cell_bar_data.set(new_bar_data_cell);
  };

  // Set up onclick handlers
  set_cell_layer_onclick(deck_yearbook, layers_obj, viz_state);
  set_path_layer_onclick(deck_yearbook, layers_obj, viz_state);
  set_trx_layer_onclick(deck_yearbook, layers_obj, viz_state);

  // Subscribe to deck_ready
  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    background_layer: true,
    cell_layer: true,
    path_layer: true,
    trx_layer: true,
  });

  viz_state.obs_store.deck_ready.subscribe((ready) => {
    if (ready) {
      const list = get_layers_list(viz_state.layers_obj, viz_state.close_up).filter(l => l !== null);
      deck_yearbook.setProps({ layers: list });
    }
  });

  // Subscribe to selection changes
  viz_state.obs_store.selected_cats.subscribe((selected_cats) => {
    const selected_cats_name = selected_cats.join('-');

    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-${selected_cats_name}-sel-${viz_state.selection_token}`,
    });

    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-${selected_cats_name}`,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: true,
      path_layer: true,
    });
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

  update_trx_layer_radius(layers_obj, 0.25);

  // Track view states for each portrait
  const viewStatesRef = {};

  // Initialize view states
  const initViewStates = () => {
    const centers = viz_state.yearbook.portrait_centers;
    const zoom = viz_state.yearbook.zoom_level;
    centers.forEach((center, index) => {
      viewStatesRef[`portrait-${index}`] = {
        target: [center.x, center.y, 0],
        zoom: zoom,
      };
    });
  };

  // Initialize portraits
  await update_all_portraits();
  initViewStates();

  // Handle page changes with debounce to prevent rapid clicks causing issues
  let isPageChanging = false;
  const handle_page_change = async (new_page) => {
    // Skip if already processing a page change
    if (isPageChanging) {
      console.log('Yearbook: Page change already in progress, skipping');
      return;
    }

    isPageChanging = true;
    try {
      viz_state.yearbook.current_page = new_page;
      await update_all_portraits();
      initViewStates();

      // Update pagination UI
      if (viz_state.yearbook.update_pagination_ui) {
        viz_state.yearbook.update_pagination_ui();
      }

      if (viz_state.model && typeof viz_state.model.set === 'function') {
        viz_state.model.set('current_page', new_page);
        viz_state.model.save_changes();
      }
    } finally {
      // Reset flag after a short delay to prevent rapid clicks
      setTimeout(() => {
        isPageChanging = false;
      }, 300);
    }
  };

  // Debounce flag to prevent recursive updates
  let isUpdatingZoom = false;

  // Sync zoom across all portraits
  const syncZoomToAllPortraits = (new_zoom) => {
    if (isUpdatingZoom) return;
    isUpdatingZoom = true;

    viz_state.yearbook.zoom_level = new_zoom;

    // Update all view states with the new zoom (keeping their individual centers)
    const centers = viz_state.yearbook.portrait_centers;
    centers.forEach((center, index) => {
      viewStatesRef[`portrait-${index}`] = {
        target: [center.x, center.y, 0],
        zoom: new_zoom,
      };
    });

    // Update scale bar
    if (viz_state.scale_bar) {
      viz_state.scale_bar.update({ zoom: new_zoom });
    }

    // Apply synced view states to deck
    deck_yearbook.setProps({
      initialViewState: { ...viewStatesRef },
    });

    // Sync to model
    if (viz_state.model && typeof viz_state.model.set === 'function') {
      viz_state.model.set('zoom_level', new_zoom);
      viz_state.model.save_changes();
    }

    // Reset flag after a short delay
    setTimeout(() => {
      isUpdatingZoom = false;
    }, 100);
  };

  // Set up view state change handler for synced zoom
  deck_yearbook.setProps({
    onViewStateChange: ({ viewState, viewId, interactionState }) => {
      const new_zoom = viewState.zoom;
      const old_zoom = viz_state.yearbook.zoom_level;

      // If zoom changed significantly, sync across all portraits
      if (Math.abs(new_zoom - old_zoom) > 0.01 && !isUpdatingZoom) {
        // Schedule sync on next frame to avoid blocking
        requestAnimationFrame(() => {
          syncZoomToAllPortraits(new_zoom);
        });
      }

      // Always return the viewState for the current view
      return viewState;
    },
  });

  // Create UI container
  const ui_container = make_yearbook_ui_container(
    dataset_name,
    deck_yearbook,
    layers_obj,
    viz_state,
    handle_page_change
  );

  // Listen for model changes
  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.on('change:current_page', () => {
      const new_page = viz_state.model.get('current_page');
      if (new_page !== viz_state.yearbook.current_page) {
        handle_page_change(new_page);
      }
    });

    viz_state.model.on('change:cells', async () => {
      viz_state.yearbook.cells = viz_state.model.get('cells');
      await update_all_portraits();
      initViewStates();
    });

    viz_state.model.on('change:zoom_level', () => {
      const new_zoom = viz_state.model.get('zoom_level');
      if (Math.abs(new_zoom - viz_state.yearbook.zoom_level) > 0.01) {
        syncZoomToAllPortraits(new_zoom);
      }
    });
  }

  // UI and Viz Container
  el.appendChild(ui_container);
  el.appendChild(root);

  const yearbook_api = {
    update_page: handle_page_change,
    refresh: async () => {
      await update_all_portraits();
      initViewStates();
    },
    finalize: () => {
      deck_yearbook.finalize();
    },
  };

  return yearbook_api;
};

