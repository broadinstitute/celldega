/**
 * Dependency definitions for breaking circular imports
 * Snake_case API to match existing codebase conventions
 */

import { createLazy } from './lazyResolver.js';

// Helper function to create import configs for a module
const createModuleImports = (modulePath, exports) => {
  const result = {};
  for (const [key, exportName] of Object.entries(exports)) {
    result[key] = {
      importFn: () => import(modulePath),
      exportName
    };
  }
  return result;
};

// Helper function to merge multiple module configs
const mergeConfigs = (...configs) => Object.assign({}, ...configs);

// Both keys and values use snake_case to match your existing code style
const cellLayerExports = {
  update_cell_layer_id: 'update_cell_layer_id',
  update_cell_layer_radius: 'update_cell_layer_radius',
  update_cell_pickable_state: 'update_cell_pickable_state',
  new_toggle_cell_layer_visibility: 'new_toggle_cell_layer_visibility',
  toggle_spatial_umap: 'toggle_spatial_umap'
};

const pathLayerExports = {
  update_path_layer_id: 'update_path_layer_id',
  update_path_pickable_state: 'update_path_pickable_state',
  toggle_path_layer_visibility: 'toggle_path_layer_visibility'
};

const trxLayerExports = {
  update_trx_layer_id: 'update_trx_layer_id',
  update_trx_layer_radius: 'update_trx_layer_radius',
  update_trx_pickable_state: 'update_trx_pickable_state',
  toggle_trx_layer_visibility: 'toggle_trx_layer_visibility'
};

const nbhdLayerExports = {
  filter_cat_nbhd_feature_collection: 'filter_cat_nbhd_feature_collection',
  toggle_nbhd_layer_visibility: 'toggle_nbhd_layer_visibility',
  update_nbhd_layer_data: 'update_nbhd_layer_data'
};

const editLayerExports = {
  update_edit_layer_mode: 'update_edit_layer_mode',
  update_edit_visitility: 'update_edit_visitility',
  calc_and_update_rgn_bar_graph: 'calc_and_update_rgn_bar_graph',
  sync_region_to_model: 'sync_region_to_model'
};

const barPlotExports = {
  bar_callback_rgn: 'bar_callback_rgn',
  update_bar_graph: 'update_bar_graph'
};

const imageLayerExports = {
  toggle_visibility_image_layers: 'toggle_visibility_image_layers',
  toggle_visibility_single_image_layer: 'toggle_visibility_single_image_layer'
};

// Single function exports (snake_case keys and values)
const singleExports = {
  // === CORE LAYER MANAGEMENT ===
  get_layers_list: {
    importFn: () => import('../deck-gl/layers_ist.js'),
    exportName: 'get_layers_list'
  },

  // === UI FUNCTIONS ===
  toggle_image_layers_and_ctrls: {
    importFn: () => import('../ui/ui_containers.js'),
    exportName: 'toggle_image_layers_and_ctrls'
  },
  update_gene_text_box: {
    importFn: () => import('../ui/gene_search.js'),
    exportName: 'update_gene_text_box'
  },

  // === BACKGROUND & VISIBILITY ===
  toggle_background_layer_visibility: {
    importFn: () => import('../deck-gl/background_layer.js'),
    exportName: 'toggle_background_layer_visibility'
  },

  // === SLIDER FUNCTIONS ===
  toggle_slider: {
    importFn: () => import('../ui/sliders.js'),
    exportName: 'toggle_slider'
  }
};

// Create the final dependencies object
export const deps = createLazy(
  mergeConfigs(
    // === Deck.gl layers ===
    createModuleImports('../deck-gl/cell_layer.js', cellLayerExports),
    createModuleImports('../deck-gl/path_layer.js', pathLayerExports),
    createModuleImports('../deck-gl/trx_layer.js', trxLayerExports),
    createModuleImports('../deck-gl/nbhd_layer.js', nbhdLayerExports),
    createModuleImports('../deck-gl/edit_layer.js', editLayerExports),

    // === UI components ===
    createModuleImports('../ui/bar_plot.js', barPlotExports),
    createModuleImports('../deck-gl/image_layers.js', imageLayerExports),

    // === Single exports ===
    singleExports
  )
);

// Export helper functions for testing or extending
export { createModuleImports, mergeConfigs };
