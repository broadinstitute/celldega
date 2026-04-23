import { AwsClient } from 'aws4fetch';

import {
  ini_deck,
  set_get_tooltip,
  set_views_prop,
} from '../deck-gl/core/deck_ist';
import {
  create_yearbook_views,
  get_discontiguous_tiles,
} from '../deck-gl/core/yearbook_viewports';
import { ini_background_layer } from '../deck-gl/layers/background_layer';
import {
  ini_cell_layer,
  set_cell_layer_onclick,
} from '../deck-gl/layers/cell_layer';
import {
  make_yearbook_image_layers,
  toggle_visibility_image_layers,
} from '../deck-gl/layers/image_layers';
import {
  ini_path_layer,
  set_path_layer_onclick,
  update_path_layer_data,
} from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  set_trx_layer_onclick,
  update_trx_layer_radius,
  update_trx_layer_data,
} from '../deck-gl/layers/trx_layer';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import { ini_cache } from '../global_variables/cache';
import { update_cat } from '../global_variables/cat';
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
import { create_obs_store } from '../obs_store/obs_store';
import { CBGRowGroupReader } from '../read_parquet/cbg_row_group_reader';
import { ImageRowGroupReader } from '../read_parquet/image_row_group_reader';
import { RowGroupTileReader } from '../read_parquet/row_group_tile_reader';
import { set_image_layer_sliders } from '../ui/sliders';
import { make_yearbook_ui_container } from '../ui/yearbook_ui';
import { execute_cell_query } from '../utils/cell_query';
import {
  areBarDataEqual,
  createEmptyCellCompact,
  createEmptyTrxCompact,
} from '../utils/compact_data';
import { refresh_layer } from '../utils/refresh_layer';
import { create_scale_bar, PIXEL_SIZE_MICRONS } from '../utils/scale_bar';

// Row group reading support

/**
 * Initialize row group readers for Yearbook if the landscape uses row groups
 * @param {Object} viz_state - Visualization state
 * @param {string} base_url - Base URL for the landscape files
 * @returns {Promise<void>}
 */
async function initializeYearbookRowGroupReaders(viz_state, base_url) {
  const landscapeParams = viz_state.img.landscape_parameters;

  if (!landscapeParams.use_row_groups) {
    viz_state.use_row_groups = false;
    return;
  }

  // console.log('[yearbook] Row group mode enabled, initializing readers...');

  const rowGroupFiles = landscapeParams.row_group_files || {};
  const tileGrid = landscapeParams.tile_grid || {};

  if (!tileGrid.num_tiles_x || !tileGrid.num_tiles_y) {
    // console.error(
    //   '[yearbook] Missing tile_grid dimensions in landscape_parameters'
    // );
    viz_state.use_row_groups = false;
    return;
  }

  viz_state.use_row_groups = true;
  viz_state.row_group_readers = {};
  viz_state.tile_grid = tileGrid;

  try {
    // Initialize transcript row group reader
    if (rowGroupFiles.transcripts) {
      // console.log(`[yearbook] Initializing transcript reader`);
      // Support both chunked (object with files array) and legacy (string path) formats
      viz_state.row_group_readers.trx = new RowGroupTileReader(
        base_url,
        tileGrid,
        rowGroupFiles.transcripts
      );
      await viz_state.row_group_readers.trx.initialize();
      // console.log('[yearbook] Transcript reader ready');
    }

    // Initialize cell segmentation row group reader
    if (rowGroupFiles.cell_segmentation) {
      // console.log(`[yearbook] Initializing cell reader`);
      // Support both chunked (object with files array) and legacy (string path) formats
      viz_state.row_group_readers.cell = new RowGroupTileReader(
        base_url,
        tileGrid,
        rowGroupFiles.cell_segmentation
      );
      await viz_state.row_group_readers.cell.initialize();
      // console.log('[yearbook] Cell reader ready');
    }

    // Initialize CBG row group reader
    if (rowGroupFiles.cbg) {
      // console.log(`[yearbook] Initializing CBG reader...`);
      viz_state.row_group_readers.cbg = new CBGRowGroupReader(
        base_url,
        rowGroupFiles.cbg
      );
      await viz_state.row_group_readers.cbg.initialize();
    }

    // Initialize image row group readers for each channel
    if (rowGroupFiles.images) {
      viz_state.row_group_readers.images = {};

      for (const [channelName, imageEntry] of Object.entries(
        rowGroupFiles.images
      )) {
        // console.log(
        //   `[yearbook] Initializing image reader for ${channelName}...`
        // );
        // Pass imageEntry directly - ImageRowGroupReader handles both:
        // - Chunked mode: object with { directory, files, zoom_info, ... }
        // - Legacy mode: string path or object with { path, zoom_info }
        viz_state.row_group_readers.images[channelName] =
          new ImageRowGroupReader(base_url, imageEntry);
        // eslint-disable-next-line no-await-in-loop
        await viz_state.row_group_readers.images[channelName].initialize();
      }
    }
  } catch {
    // Error initializing row group readers - fall back to non-row-group mode
    viz_state.use_row_groups = false;
  }
}

/**
 * Calculate initial zoom level based on portrait size in micrometers
 */
const calc_initial_zoom = (
  portrait_size_um,
  portrait_pixel_size,
  micronsPerPixel
) => {
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
  current_page = 0,
  query = {},
  cell_name_prefix = false
) => {
  if (width === 0) {
    width = '100%';
  }

  const viz_state = {};

  viz_state.obs_store = create_obs_store();
  viz_state.highlighted_cells = new Set();
  viz_state.selection_token = 0;

  // Store cell_name_prefix for cell name matching
  viz_state.cell_name_prefix = cell_name_prefix;

  // Yearbook-specific state
  viz_state.yearbook = {
    cells,
    num_rows,
    num_cols,
    portrait_size_um,
    portrait_gap,
    current_page,
    zoom_level: 0,
    portrait_centers: [], // Will store the center coordinates for each portrait
    query, // Query object for finding cells from LandscapeFiles
    lastGeneBarData: null,
    lastCellBarData: null,
    geneCountScratch: null,
    activeGeneIds: [],
    cellCountScratch: null,
    activeCellIds: [],
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
  viz_state.genes.selected_gene_ids = new Set();
  viz_state.genes.trx_ini_radius = 0.25;
  viz_state.genes.trx_gene_ids = new Int32Array();
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
  viz_state.nbhd.feature_collection = {
    type: 'FeatureCollection',
    features: [],
  };

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

  // Initialize row group readers if enabled
  await initializeYearbookRowGroupReaders(viz_state, base_url);

  const tmp_image_info = viz_state.img.landscape_parameters.image_info;
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

  // Define process_query function (used after cell layer init and for model changes)
  const process_query = async (query_obj) => {
    if (!query_obj || Object.keys(query_obj).length === 0) {
      return [];
    }

    // Default max_cells based on grid size (10 pages worth)
    const default_max_cells = num_rows * num_cols * 10;

    try {
      const queried_cells = await execute_cell_query(
        query_obj,
        viz_state,
        default_max_cells
      );
      return queried_cells;
    } catch {
      // Silently handle cell query failures
      return [];
    }
  };

  // Initialize cell and trx caches
  viz_state.cache = {};
  viz_state.cache.cell = await ini_cache();
  viz_state.cache.trx = await ini_cache();

  viz_state.combo_data = {};
  viz_state.combo_data.trx = [];
  viz_state.combo_data.trx_compact = createEmptyTrxCompact();
  viz_state.combo_data.cell_compact = createEmptyCellCompact();
  viz_state.tooltip_cat_cell = '';

  // Edit state (not used in yearbook but needed for layer compatibility)
  viz_state.edit = {};
  viz_state.edit.feature_collection = {
    type: 'FeatureCollection',
    features: [],
  };
  viz_state.edit.visible = false;

  // Calculate portrait dimensions FIRST (needed for image layer setup)
  const actual_width =
    typeof width === 'string' ? el.clientWidth || 1000 : width;
  const available_width = actual_width - (num_cols - 1) * portrait_gap;
  const available_height = height - 100 - (num_rows - 1) * portrait_gap; // 100 for control panel
  const portrait_pixel_width = available_width / num_cols;
  const portrait_pixel_height = available_height / num_rows;
  const portrait_pixel_size = Math.min(
    portrait_pixel_width,
    portrait_pixel_height
  );

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
  const image_layers = []; // Will be populated with per-portrait layers
  const cell_layer = await ini_cell_layer(base_url, viz_state);
  const path_layer = await ini_path_layer(viz_state);
  const trx_layer = ini_trx_layer(viz_state);

  // Process initial query or grab random cells if none provided
  // This must happen after ini_cell_layer which populates cell_names_array and dict_cell_cats
  if (viz_state.yearbook.cells.length === 0) {
    let initial_cells = [];

    if (Object.keys(query).length > 0) {
      // Query provided - execute it
      initial_cells = await process_query(query);
    } else {
      // No cells and no query - grab random cells as fallback
      const all_cells = viz_state.cats.cell_names_array || [];
      const default_count = num_rows * num_cols * 10; // 10 pages worth

      if (all_cells.length > 0) {
        // Shuffle and take a subset
        const shuffled = [...all_cells].sort(() => Math.random() - 0.5);
        initial_cells = shuffled.slice(
          0,
          Math.min(default_count, all_cells.length)
        );
      }
    }

    viz_state.yearbook.cells = initial_cells;

    // Sync back to model if available
    if (viz_state.model && typeof viz_state.model.set === 'function') {
      viz_state.model.set('cells', initial_cells);
      viz_state.model.save_changes();
    }
  }

  // Create deck instance with multiple views
  const views = create_yearbook_views(
    num_rows,
    num_cols,
    portrait_pixel_size,
    portrait_gap
  );
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

  // Track view states for each portrait
  const viewStatesRef = {};

  // Update bar graphs based on data in all visible portraits
  const update_bar_graphs = () => {
    const centers = viz_state.yearbook.portrait_centers;
    const { portrait_data_size } = viz_state.yearbook;
    // Use half the portrait data size as the radius for filtering
    const half_view_size = portrait_data_size / 2;

    // Filter transcripts visible in any portrait using compact buffers
    const trxCompact =
      viz_state.combo_data.trx_compact || createEmptyTrxCompact();
    const geneCountLength = viz_state.genes.gene_names.length;

    if (
      !viz_state.yearbook.geneCountScratch ||
      viz_state.yearbook.geneCountScratch.length !== geneCountLength
    ) {
      viz_state.yearbook.geneCountScratch = new Uint32Array(geneCountLength);
      viz_state.yearbook.activeGeneIds = [];
    }

    const geneCounts = viz_state.yearbook.geneCountScratch;
    const activeGeneIds = viz_state.yearbook.activeGeneIds;
    activeGeneIds.length = 0;

    for (let i = 0; i < trxCompact.geneIds.length; i++) {
      const positions = trxCompact.positions;
      const x = positions[i * trxCompact.size];
      const y = positions[i * trxCompact.size + 1];
      const inPortrait = centers.some((center) => {
        return (
          x >= center.x - half_view_size &&
          x <= center.x + half_view_size &&
          y >= center.y - half_view_size &&
          y <= center.y + half_view_size
        );
      });
      if (!inPortrait) {
        continue;
      }

      const geneId = trxCompact.geneIds[i];
      if (geneId < 0) {
        continue;
      }

      if (geneCounts[geneId] === 0) {
        activeGeneIds.push(geneId);
      }
      geneCounts[geneId] += 1;
    }

    activeGeneIds.sort((a, b) => geneCounts[b] - geneCounts[a]);
    const new_bar_data = activeGeneIds.slice(0, 100).map((geneId) => ({
      name: viz_state.genes.g_nameMapping_inv?.[geneId] ?? String(geneId),
      value: geneCounts[geneId],
    }));

    for (const geneId of activeGeneIds) {
      geneCounts[geneId] = 0;
    }

    if (!areBarDataEqual(viz_state.yearbook.lastGeneBarData, new_bar_data)) {
      viz_state.yearbook.lastGeneBarData = new_bar_data;
      viz_state.obs_store.new_gene_bar_data.set(new_bar_data);
    }

    // Filter cells visible in any portrait
    const cellCompact =
      viz_state.combo_data.cell_compact || createEmptyCellCompact();
    const categoryCountLength = cellCompact.categoryNames.length;

    if (
      !viz_state.yearbook.cellCountScratch ||
      viz_state.yearbook.cellCountScratch.length !== categoryCountLength
    ) {
      viz_state.yearbook.cellCountScratch = new Uint32Array(categoryCountLength);
      viz_state.yearbook.activeCellIds = [];
    }

    const cellCounts = viz_state.yearbook.cellCountScratch;
    const activeCellIds = viz_state.yearbook.activeCellIds;
    activeCellIds.length = 0;

    for (let i = 0; i < cellCompact.categoryIds.length; i++) {
      const positions = cellCompact.positions;
      const x = positions[i * cellCompact.size];
      const y = positions[i * cellCompact.size + 1];
      const inPortrait = centers.some((center) => {
        return (
          x >= center.x - half_view_size &&
          x <= center.x + half_view_size &&
          y >= center.y - half_view_size &&
          y <= center.y + half_view_size
        );
      });
      if (!inPortrait) {
        continue;
      }

      const categoryId = cellCompact.categoryIds[i];
      if (cellCounts[categoryId] === 0) {
        activeCellIds.push(categoryId);
      }
      cellCounts[categoryId] += 1;
    }

    activeCellIds.sort((a, b) => cellCounts[b] - cellCounts[a]);
    const new_bar_data_cell = activeCellIds.map((categoryId) => ({
      name: cellCompact.categoryNames[categoryId],
      value: cellCounts[categoryId],
    }));

    for (const categoryId of activeCellIds) {
      cellCounts[categoryId] = 0;
    }

    if (
      !areBarDataEqual(viz_state.yearbook.lastCellBarData, new_bar_data_cell)
    ) {
      viz_state.yearbook.lastCellBarData = new_bar_data_cell;
      viz_state.obs_store.new_cell_bar_data.set(new_bar_data_cell);
    }
  };

  // Calculate portrait centers based on cell positions
  const update_portrait_centers = async () => {
    const portraits_per_page = num_rows * num_cols;
    // Use viz_state values which get updated by pagination/model changes
    const inst_current_page = viz_state.yearbook.current_page;
    const inst_cells = viz_state.yearbook.cells;
    const start_index = inst_current_page * portraits_per_page;
    const page_cells = inst_cells.slice(
      start_index,
      start_index + portraits_per_page
    );

    // Get cell positions from the scatter data
    const centers = page_cells.map((cell_id) => {
      const cell_index = viz_state.cats.cell_name_to_index_map.get(cell_id);
      if (
        cell_index !== undefined &&
        viz_state.spatial.cell_scatter_data_objects
      ) {
        const cell_data =
          viz_state.spatial.cell_scatter_data_objects[cell_index];
        if (cell_data && cell_data.position) {
          return {
            cell_id,
            x: cell_data.position[0],
            y: cell_data.position[1],
          };
        }
      }
      // Fallback to center of image if cell not found
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

    // Apply current image visibility state to the new layers
    const current_viz_image_layers = viz_state.obs_store.viz_image_layers.get();
    toggle_visibility_image_layers(layers_obj, current_viz_image_layers);

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
    const layers_list = get_layers_list(layers_obj, viz_state.close_up).filter(
      (l) => l !== null
    );

    // Apply all changes at once
    deck_yearbook.setProps({
      initialViewState: view_states,
      layers: layers_list,
    });

    // Update bar graphs based on visible data
    update_bar_graphs();

    // Update scale bar
    if (viz_state.scale_bar) {
      viz_state.scale_bar.update({ zoom: zoom_level });
    }
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
      const list = get_layers_list(
        viz_state.layers_obj,
        viz_state.close_up
      ).filter((l) => l !== null);
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

  // Initialize view states
  const initViewStates = () => {
    const centers = viz_state.yearbook.portrait_centers;
    const zoom = viz_state.yearbook.zoom_level;
    centers.forEach((center, index) => {
      viewStatesRef[`portrait-${index}`] = {
        target: [center.x, center.y, 0],
        zoom,
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
    onViewStateChange: ({ viewState }) => {
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

  // Handle query changes from UI
  const handle_query_change = async (new_query) => {
    viz_state.yearbook.query = new_query;

    // Update status in UI
    if (viz_state.yearbook.query_ui) {
      viz_state.yearbook.query_ui.update_status('Searching...');
    }

    try {
      // Update gene state if query includes a gene
      if (new_query.gene) {
        const inst_gene = new_query.gene;

        // Update category to gene mode
        update_cat(viz_state.cats, inst_gene);

        // Force-set selected genes (bypass toggle behavior)
        viz_state.genes.selected_genes = [inst_gene];
        viz_state.obs_store.selected_genes.set([inst_gene]);

        // Load gene expression data for cell coloring
        await update_cell_exp_array(
          viz_state.cats,
          viz_state.genes,
          viz_state.global_base_url,
          inst_gene,
          viz_state.seg.version,
          viz_state.vector_name_integer,
          viz_state.aws,
          viz_state.row_group_readers?.cbg
        );

        // Force-set selected_cats (bypass toggle behavior)
        viz_state.cats.selected_cats = [inst_gene];
        viz_state.obs_store.selected_cats.set([inst_gene]);

        // Refresh layers to apply gene filtering/coloring
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      } else {
        // No gene - reset to cluster mode
        update_cat(viz_state.cats, 'cluster');

        // Force-clear selections
        viz_state.genes.selected_genes = [];
        viz_state.obs_store.selected_genes.set([]);
        viz_state.cats.selected_cats = [];
        viz_state.obs_store.selected_cats.set([]);

        // Refresh layers to reset to cluster mode
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      }

      const queried_cells = await process_query(new_query);
      viz_state.yearbook.cells = queried_cells;

      // Update status with result count
      if (viz_state.yearbook.query_ui) {
        const count = queried_cells.length;
        viz_state.yearbook.query_ui.update_status(`Found ${count} cells`);
      }

      // Sync to model if available
      if (viz_state.model && typeof viz_state.model.set === 'function') {
        viz_state.model.set('cells', queried_cells);
        viz_state.model.set('query', new_query);
        viz_state.model.set('current_page', 0);
        viz_state.model.save_changes();
      }

      // Reset to first page and update portraits
      viz_state.yearbook.current_page = 0;
      await update_all_portraits();
      initViewStates();

      if (viz_state.yearbook.update_pagination_ui) {
        viz_state.yearbook.update_pagination_ui();
      }
    } catch {
      // Handle query failure gracefully
      if (viz_state.yearbook.query_ui) {
        viz_state.yearbook.query_ui.update_status('Query failed');
      }
    }
  };

  // Create UI container
  const ui_container = make_yearbook_ui_container(
    dataset_name,
    deck_yearbook,
    layers_obj,
    viz_state,
    handle_page_change,
    handle_query_change
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

    viz_state.model.on('change:query', async () => {
      const new_query = viz_state.model.get('query') || {};
      viz_state.yearbook.query = new_query;

      // Update query UI inputs to reflect the new query
      if (viz_state.yearbook.query_ui) {
        const { cluster_input, gene_input, update_status } =
          viz_state.yearbook.query_ui;
        if (new_query.cluster) {
          cluster_input.value = new_query.cluster.value || '';
        } else {
          cluster_input.value = '';
        }
        if (new_query.gene) {
          gene_input.value = new_query.gene || '';
        } else {
          gene_input.value = '';
        }
        update_status('Searching...');
      }

      // Execute the new query
      if (Object.keys(new_query).length > 0) {
        // Update gene state if query includes a gene
        if (new_query.gene) {
          const inst_gene = new_query.gene;

          // Update category to gene mode
          update_cat(viz_state.cats, inst_gene);

          // Force-set selected genes (bypass toggle behavior)
          viz_state.genes.selected_genes = [inst_gene];
          viz_state.obs_store.selected_genes.set([inst_gene]);

          // Load gene expression data for cell coloring
          await update_cell_exp_array(
            viz_state.cats,
            viz_state.genes,
            viz_state.global_base_url,
            inst_gene,
            viz_state.seg.version,
            viz_state.vector_name_integer,
            viz_state.aws
          );

          // Force-set selected_cats (bypass toggle behavior)
          viz_state.cats.selected_cats = [inst_gene];
          viz_state.obs_store.selected_cats.set([inst_gene]);

          // Refresh layers to apply gene filtering/coloring
          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'trx_layer');
        } else {
          // No gene - reset to cluster mode
          update_cat(viz_state.cats, 'cluster');

          // Force-clear selections
          viz_state.genes.selected_genes = [];
          viz_state.obs_store.selected_genes.set([]);
          viz_state.cats.selected_cats = [];
          viz_state.obs_store.selected_cats.set([]);

          // Refresh layers to reset to cluster mode
          refresh_layer(viz_state, layers_obj, 'cell_layer');
          refresh_layer(viz_state, layers_obj, 'trx_layer');
        }

        const queried_cells = await process_query(new_query);
        viz_state.yearbook.cells = queried_cells;

        // Update status
        if (viz_state.yearbook.query_ui) {
          viz_state.yearbook.query_ui.update_status(
            `Found ${queried_cells.length} cells`
          );
        }

        // Sync cells back to model
        viz_state.model.set('cells', queried_cells);
        viz_state.model.save_changes();

        // Reset to first page and update portraits
        viz_state.yearbook.current_page = 0;
        viz_state.model.set('current_page', 0);

        await update_all_portraits();
        initViewStates();

        if (viz_state.yearbook.update_pagination_ui) {
          viz_state.yearbook.update_pagination_ui();
        }
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
    /**
     * Update the yearbook query and refresh the display.
     * @param {Object} new_query - Query object with optional cluster and gene
     * @param {Object} [new_query.cluster] - Cluster filter { attr: 'leiden', value: '1' }
     * @param {string} [new_query.gene] - Gene to rank cells by expression
     * @param {number} [new_query.max_cells] - Maximum cells to return
     */
    update_query: async (new_query) => {
      await handle_query_change(new_query);
    },
    /**
     * Update query to show cells from a specific cluster.
     * @param {string} cluster_value - Cluster identifier (e.g., '1', '5')
     * @param {string} [cluster_attr='leiden'] - Cluster attribute name
     */
    update_cluster: async (cluster_value, cluster_attr = 'leiden') => {
      const current_query = viz_state.yearbook.query || {};
      const new_query = {
        ...current_query,
        cluster: { attr: cluster_attr, value: String(cluster_value) },
      };
      await handle_query_change(new_query);
    },
    /**
     * Update query to rank cells by gene expression.
     * @param {string} gene_name - Gene name to rank by
     */
    update_gene: async (gene_name) => {
      const current_query = viz_state.yearbook.query || {};
      const new_query = {
        ...current_query,
        gene: gene_name,
      };
      await handle_query_change(new_query);
    },
    /**
     * Get the current query state.
     * @returns {Object} Current query object
     */
    get_query: () => {
      return viz_state.yearbook.query || {};
    },
    finalize: () => {
      deck_yearbook.finalize();
    },
  };

  return yearbook_api;
};
