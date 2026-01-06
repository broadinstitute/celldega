import './celldega.css';

import { networkFromDegaFiles } from './read_parquet/network_from_dega_files';
import { networkFromParquet } from './read_parquet/network_from_parquet';
import { objects_from_parquet } from './read_parquet/objects_from_parquet';
import {
  handleAsyncError,
  handleValidationWarning,
} from './temp_utils/errorHandler';
import { landscape_h_e } from './viz/landscape_h_e';
import { landscape_ist } from './viz/landscape_ist';
import { landscape_sst } from './viz/landscape_sst';
import { matrix_viz } from './viz/matrix_viz';
import { yearbook } from './viz/yearbook';
import { render_enrich } from './widgets/enrich_widget';

// Remove export keywords from render functions
const render_landscape_ist = async ({ model, el }) => {
  const token = model.get('token');
  const creds = model.get('creds');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const base_urls = model.get('base_urls') || [];
  const cell_name_prefix = model.get('cell_name_prefix') || false;
  const dataset_name = model.get('dataset_name');
  const width = model.get('width');
  const height = model.get('height');
  const rotation_orbit = model.get('rotation_orbit') ?? 0;
  const rotation_x = model.get('rotation_x') ?? 0;
  const rotate = model.get('rotate') ?? 0;
  const nbhd = model.get('nbhd_geojson');
  const max_tiles_to_view = model.get('max_tiles_to_view');
  const nbhd_edit = model.get('nbhd_edit');
  const scale_bar_microns_per_pixel = model.get('scale_bar_microns_per_pixel');

  let meta_cell_data = { result: {}, attr: [] };
  let meta_cluster_data = { result: {}, attr: [] };
  let umap_data = {};

  const metaCellBytes = model.get('meta_cell_parquet');
  if (metaCellBytes && metaCellBytes.byteLength > 0) {
    meta_cell_data = await objects_from_parquet(metaCellBytes, 'cell_id');
  }

  const metaClusterBytes = model.get('meta_cluster_parquet');
  if (metaClusterBytes && metaClusterBytes.byteLength > 0) {
    meta_cluster_data = await objects_from_parquet(metaClusterBytes, 'leiden');
  }

  const umapBytes = model.get('umap_parquet');
  if (umapBytes && umapBytes.byteLength > 0) {
    umap_data = (await objects_from_parquet(umapBytes, 'cell_id')).result;
  }

  const technology = model.get('technology');
  let landscape_state = model.get('landscape_state');
  if (technology === 'Chromium') {
    landscape_state = 'umap';
  } else if (technology === 'point-cloud') {
    landscape_state = 'spatial';
  }
  const segmentation = model.get('segmentation');

  return landscape_ist(
    el,
    model,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    base_url,
    dataset_name,
    0.25,
    width,
    height,
    meta_cell_data.result,
    meta_cell_data.attr,
    meta_cluster_data.result,
    meta_cluster_data.attr,
    umap_data,
    nbhd,
    nbhd_edit,
    landscape_state,
    segmentation,
    creds,
    null,
    rotation_orbit,
    rotation_x,
    rotate,
    max_tiles_to_view,
    scale_bar_microns_per_pixel,
    base_urls,
    cell_name_prefix
  );
};

const render_landscape_sst = async ({ model, el }) => {
  const token = model.get('token');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const square_tile_size = model.get('square_tile_size');
  const width = model.get('width');
  const height = model.get('height');

  landscape_sst(
    model,
    el,
    base_url,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    square_tile_size,
    dataset_name,
    width,
    height
  );
};

const render_landscape_h_e = async ({ model, el }) => {
  const token = model.get('token');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const width = model.get('width');
  const height = model.get('height');
  const creds = model.get('creds');

  landscape_h_e(
    model,
    el,
    base_url,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    dataset_name,
    width,
    height,
    creds
  );
};

const render_landscape = async ({ model, el }) => {
  const technology = model.get('technology');

  if (
    ['MERSCOPE', 'Xenium', 'Chromium', 'point-cloud', 'Visium-HD'].includes(
      technology
    )
  ) {
    return render_landscape_ist({ model, el });
  } else if (['Visium-HD-no-jitter'].includes(technology)) {
    return render_landscape_sst({ model, el });
  } else if (['h&e'].includes(technology)) {
    return render_landscape_h_e({ model, el });
  }
};

const render_yearbook = async ({ model, el }) => {
  const token = model.get('token');
  const creds = model.get('creds');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const width = model.get('width');
  const height = model.get('height');
  const cells = model.get('cells') || [];
  const num_rows = model.get('num_rows') || 2;
  const num_cols = model.get('num_cols') || 3;
  const portrait_size_um = model.get('portrait_size_um') || 100;
  const portrait_gap = model.get('portrait_gap') || 4;
  const segmentation = model.get('segmentation') || 'default';
  const scale_bar_microns_per_pixel = model.get('scale_bar_microns_per_pixel');
  const current_page = model.get('current_page') || 0;
  const query = model.get('query') || {};
  const cell_name_prefix = model.get('cell_name_prefix') || false;

  let meta_cell_data = { result: {}, attr: [] };
  let meta_cluster_data = { result: {}, attr: [] };

  const metaCellBytes = model.get('meta_cell_parquet');
  if (metaCellBytes && metaCellBytes.byteLength > 0) {
    meta_cell_data = await objects_from_parquet(metaCellBytes, 'cell_id');
  }

  const metaClusterBytes = model.get('meta_cluster_parquet');
  if (metaClusterBytes && metaClusterBytes.byteLength > 0) {
    meta_cluster_data = await objects_from_parquet(metaClusterBytes, 'leiden');
  }

  return yearbook(
    el,
    model,
    token,
    base_url,
    dataset_name,
    cells,
    num_rows,
    num_cols,
    portrait_size_um,
    portrait_gap,
    width,
    height,
    meta_cell_data.result,
    meta_cell_data.attr,
    meta_cluster_data.result,
    meta_cluster_data.attr,
    segmentation,
    creds,
    scale_bar_microns_per_pixel,
    current_page,
    query,
    cell_name_prefix
  );
};

const render_matrix_new = async ({ model, el }) => {
  // let network = model.get('network');
  let network;
  const width = model.get('width');
  const height = model.get('height');

  const matBytes = model.get('mat_parquet');
  if (matBytes && matBytes.byteLength > 0) {
    network = await networkFromParquet(
      model.get('network_meta'),
      matBytes,
      model.get('row_nodes_parquet'),
      model.get('col_nodes_parquet'),
      model.get('row_linkage_parquet'),
      model.get('col_linkage_parquet'),
      model.get('row_entity'),
      model.get('col_entity')
    );
  }

  return matrix_viz(model, el, network, width, height);
};

// Main render function - no export keyword
async function render({ model, el }) {
  let cleanup = null;
  try {
    const componentType = model.get('component');

    // Add null/undefined checks
    if (!componentType) {
      handleValidationWarning('Component type is not defined', {
        data: { model: model?.id || 'unknown', el: el?.id || 'unknown' },
      });
      return;
    }

    switch (componentType) {
      case 'Landscape':
        cleanup = await render_landscape({ model, el });
        break;
      case 'Yearbook':
        cleanup = await render_yearbook({ model, el });
        break;
      case 'Matrix':
        // return render_matrix_new({ model, el });
        cleanup = await render_matrix_new({ model, el });
        break;
      case 'Enrich':
        cleanup = await render_enrich({ model, el });
        break;
      default:
        handleValidationWarning(`Unknown component type: ${componentType}`, {
          data: { componentType, model: model?.id || 'unknown' },
        });
        return;
    }

    model.on('msg:custom', (msg) => {
      if (msg.event === 'finalize' && cleanup) {
        try {
          if (typeof cleanup === 'function') {
            cleanup();
          } else if (cleanup.finalize) {
            cleanup.finalize();
          }
        } catch (e) {
          handleValidationWarning('Error finalizing deck', {
            data: { error: e.message, model: model?.id || 'unknown' },
          });
        }
        cleanup = null;
      }
    });
  } catch (error) {
    const errorResult = handleAsyncError(error, {
      context: 'render function',
      logUnexpected: true,
      messages: {
        unexpected: 'Error in render function',
      },
    });

    // Create error display in the element
    el.innerHTML = `<div style="color: red; padding: 10px;">Error: ${errorResult.message}</div>`;
  }
}

/**
 * Load and render a Clustergram from DegaFiles.
 *
 * @param {HTMLElement} el - Container element for the visualization
 * @param {string} base_url - Base URL for the DegaFiles directory
 * @param {string} name - Name of the Clustergram (subdirectory under cgm/)
 * @param {number} width - Width of the visualization
 * @param {number} height - Height of the visualization
 * @param {function} [row_label_callback] - Callback for gene/row click events
 * @param {function} [col_label_callback] - Callback for cluster/column click events
 * @param {function} [col_dendro_callback] - Callback for dendrogram selection events
 * @param {object} [options] - Optional fetch options for authentication
 * @returns {Promise<object>} - The matrix visualization object
 */
const matrix_from_dega_files = async (
  el,
  base_url,
  name = 'default',
  width = 500,
  height = 500,
  row_label_callback = null,
  col_label_callback = null,
  col_dendro_callback = null,
  options = {}
) => {
  const network = await networkFromDegaFiles(base_url, name, options);

  // Create a minimal model-like object for matrix_viz
  const model = {
    get: (key) => {
      if (key === 'row_entity') {
        return JSON.stringify(
          network.row_entity || { entity: 'gene', attr: 'name' }
        );
      }
      if (key === 'col_entity') {
        return JSON.stringify(
          network.col_entity || { entity: 'cell', attr: 'leiden' }
        );
      }
      return null;
    },
    set: () => {},
    save_changes: () => {},
    on: () => {},
  };

  return matrix_viz(
    model,
    el,
    network,
    width,
    height,
    row_label_callback,
    col_label_callback,
    col_dendro_callback
  );
};

export default {
  landscape_ist,
  landscape_sst,
  landscape_h_e,
  matrix_viz,
  matrix_from_dega_files,
  networkFromDegaFiles,
  yearbook,
  render,
  render_landscape_ist,
  render_landscape_sst,
  render_landscape_h_e,
  render_landscape,
  render_yearbook,
  render_matrix_new,
  render_enrich,
};
