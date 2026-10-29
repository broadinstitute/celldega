import { is_orbit_technology } from './global_variables/image_info';
import {
  buildCellSlice,
  buildColAxisSlice,
  buildRowAxisSlice,
  emitMatrixSliceRequest,
} from './matrix/matrix_axis_slice';
import { networkFromDegaFiles } from './read_parquet/network_from_dega_files';
import { networkFromParquet } from './read_parquet/network_from_parquet';
import { objects_from_parquet } from './read_parquet/objects_from_parquet';
import { anndata_zarr_source } from './read_zarr/anndata_zarr';
import { network_from_zarr } from './read_zarr/network_from_zarr';
import {
  handleAsyncError,
  handleValidationWarning,
} from './temp_utils/errorHandler';
import { link_models, make_options_model } from './utils/options_model';
import { landmark } from './viz/landmark';
import { landscape_h_e } from './viz/landscape_h_e';
import { landscape_ist } from './viz/landscape_ist';
import { landscape_model_values } from './viz/landscape_options';
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
  const cell_size = model.get('cell_size') ?? 10;
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

  const clusterAttr = model.get('cluster_attr') || 'leiden';
  const metaClusterBytes = model.get('meta_cluster_parquet');
  if (metaClusterBytes && metaClusterBytes.byteLength > 0) {
    meta_cluster_data = await objects_from_parquet(
      metaClusterBytes,
      clusterAttr
    );
  }

  const umapBytes = model.get('umap_parquet');
  if (umapBytes && umapBytes.byteLength > 0) {
    umap_data = (await objects_from_parquet(umapBytes, 'cell_id')).result;
  }

  // Single-cell data from an AnnData Zarr store instead of DegaFiles. Metadata
  // Python sent from an in-memory AnnData takes precedence over the store's.
  const zarr_url = model.get('zarr_url');
  let single_cell_source = null;
  if (zarr_url) {
    single_cell_source = await anndata_zarr_source(zarr_url, {
      layer: model.get('zarr_layer') || '',
      cell_attr: model.get('cell_attr') || [],
      cluster_attr: clusterAttr,
    });
    if (meta_cell_data.attr.length === 0) {
      meta_cell_data = single_cell_source.meta_cell;
    }
    if (meta_cluster_data.attr.length === 0) {
      meta_cluster_data = single_cell_source.meta_cluster;
    }
    if (Object.keys(umap_data).length === 0) {
      umap_data = single_cell_source.umap ?? {};
    }
    if (meta_cell_data.attr.length === 0) {
      throw new Error(
        `[Landscape] cluster_attr "${clusterAttr}" is not an obs column of ${zarr_url}; pass cluster_attr=... or adata=...`
      );
    }
  }

  let centroids_data = {};
  const use_adata_3d_centroids = model.get('use_adata_3d_centroids') || false;
  const centroidsUrl = model.get('centroids_url') || '';
  if (centroidsUrl) {
    // Millions of per-cell centroids don't fit through the widget comm
    // channel, so they're served as a plain file (same as cell_metadata.parquet)
    // instead of synced through model state — see `centroids_url` in widget.py.
    const response = await fetch(centroidsUrl);
    const centroidsBytes = new Uint8Array(await response.arrayBuffer());
    centroids_data = (await objects_from_parquet(centroidsBytes, 'cell_id'))
      .result;
  } else {
    const centroidsBytes = model.get('centroids_parquet');
    if (centroidsBytes && centroidsBytes.byteLength > 0) {
      centroids_data = (await objects_from_parquet(centroidsBytes, 'cell_id'))
        .result;
    }
  }

  const technology = model.get('technology');
  let landscape_state = model.get('landscape_state');
  if (technology === 'Chromium') {
    landscape_state = landscape_state === 'xy' ? 'xy' : 'umap';
  } else if (is_orbit_technology(technology)) {
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
    cell_name_prefix,
    centroids_data,
    use_adata_3d_centroids,
    cell_size,
    single_cell_source
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

  return landscape_h_e(
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
    ['MERSCOPE', 'Xenium', 'Chromium', 'Visium-HD'].includes(technology) ||
    is_orbit_technology(technology)
  ) {
    return render_landscape_ist({ model, el });
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
  const query = model.get('front_end_query') || {};
  const cell_name_prefix = model.get('cell_name_prefix') || false;

  let meta_cell_data = { result: {}, attr: [] };
  let meta_cluster_data = { result: {}, attr: [] };

  const metaCellBytes = model.get('meta_cell_parquet');
  if (metaCellBytes && metaCellBytes.byteLength > 0) {
    meta_cell_data = await objects_from_parquet(metaCellBytes, 'cell_id');
  }

  const clusterAttr = model.get('cluster_attr') || 'leiden';
  const metaClusterBytes = model.get('meta_cluster_parquet');
  if (metaClusterBytes && metaClusterBytes.byteLength > 0) {
    meta_cluster_data = await objects_from_parquet(
      metaClusterBytes,
      clusterAttr
    );
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

const render_landmark = async ({ model, el }) => landmark(model, el);

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
      model.get('dot_mat_parquet')
    );
  }

  return matrix_viz(model, el, network, width, height);
};

// Main render function - no export keyword
async function render({ model, el }) {
  let cleanup = null;
  let finalized = false;

  const finalize = () => {
    if (finalized) return;
    finalized = true;

    try {
      if (typeof cleanup === 'function') {
        cleanup();
      } else if (cleanup?.finalize) {
        cleanup.finalize();
      }
    } catch (error) {
      handleValidationWarning('Error finalizing widget', {
        data: { error: error.message, model: model?.id || 'unknown' },
      });
    } finally {
      cleanup = null;
    }
  };

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
      case 'CellCloud':
      case 'NeighborhoodCloud':
        // 3D-orbit widgets reuse the ist render path; the orbit view, layers,
        // and manifest filename are driven by the model's technology /
        // manifest_name traits (see render_landscape_ist and landscape_ist).
        cleanup = await render_landscape_ist({ model, el });
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
      case 'Landmark':
        cleanup = await render_landmark({ model, el });
        break;
      default:
        handleValidationWarning(`Unknown component type: ${componentType}`, {
          data: { componentType, model: model?.id || 'unknown' },
        });
        return;
    }

    const on_finalize_message = (msg) => {
      if (msg.event === 'finalize') finalize();
    };
    model.on('msg:custom', on_finalize_message);

    // anywidget invokes the function returned by render whenever this view is
    // removed or rerendered. Keep the explicit custom-message path above for
    // Python's widget.close(), but route both paths through the same idempotent
    // finalizer.
    let disposed = false;
    return () => {
      if (disposed) return;
      disposed = true;
      model.off?.('msg:custom', on_finalize_message);
      finalize();
    };
  } catch (error) {
    finalize();
    const errorResult = handleAsyncError(error, {
      context: 'render function',
      logUnexpected: true,
      messages: {
        unexpected: 'Error in render function',
      },
    });

    // Create error display in the element
    el.innerHTML = `<div style="color: red; padding: 10px;">Error: ${errorResult.message}</div>`;
    return undefined;
  }
}

// The widget model a Clustergram renders with when there is no Python kernel.
const static_matrix_model = (
  network,
  { viz_mode = null, rank_dim = null } = {}
) =>
  make_options_model({
    row_entity: JSON.stringify(
      network.row_entity || { entity: 'gene', attr: 'name' }
    ),
    col_entity: JSON.stringify(
      network.col_entity || { entity: 'cell', attr: 'leiden' }
    ),
    viz_mode,
    rank_dim,
  });

/**
 * Render a Landscape in a web page, without Python. The options are the
 * Python `Landscape`'s arguments, with the same defaults; for example a
 * single-cell AnnData Zarr store:
 * `await landscape(el, { zarr_url, cluster_attr: 'leiden', ini_zoom: -4.5 })`.
 *
 * @param {HTMLElement} el - Container element for the visualization
 * @param {object} options - e.g. `zarr_url` or `base_url`, `cluster_attr`,
 *   `cell_attr`, `technology`, `ini_x`, `ini_y`, `ini_zoom`, `height`, `width`
 * @returns {Promise<object>} The Landscape, with its `model` (see link_models)
 *   and `finalize()`
 */
const landscape = async (el, options = {}) => {
  const model = make_options_model(landscape_model_values(options));
  const viz = await render_landscape_ist({ model, el });
  viz.model = model;
  return viz;
};

/**
 * Render a Clustergram in a web page, without Python, from a `network`
 * object, a clustered Matrix Zarr store (`url`, written with
 * `Matrix.write_zarr`), or DegaFiles (`base_url` and `name`).
 *
 * @param {HTMLElement} el - Container element for the visualization
 * @param {object} options
 * @param {object} [options.network] - A Clustergram network object
 * @param {string} [options.url] - URL of a clustered Matrix `.zarr` store
 * @param {string} [options.base_url] - Base URL of DegaFiles
 * @param {string} [options.name='default'] - DegaFiles Clustergram name
 * @param {number} [options.width=500] - Width of the matrix
 * @param {number} [options.height=500] - Height of the matrix
 * @param {string} [options.viz_mode] - 'heatmap' or 'dotplot'; defaults to
 *   'dotplot' when the network has a size matrix
 * @param {number} [options.rank_dim] - Open at this precomputed view level
 *   (e.g. 10 top markers per cluster), like Python's `Clustergram(rank_dim=)`;
 *   the full matrix by default
 * @param {function} [options.row_label_callback] - Called with a clicked row name
 * @param {function} [options.col_label_callback] - Called with a clicked column name
 * @param {function} [options.col_dendro_callback] - Called on dendrogram selections
 * @param {object} [options.fetchOptions] - Options for every fetch, e.g. headers
 * @returns {Promise<object>} The Clustergram, with its `model` (see
 *   link_models) and `finalize()`
 */
const clustergram = async (
  el,
  {
    network: given_network,
    url,
    base_url,
    name = 'default',
    width = 500,
    height = 500,
    viz_mode,
    rank_dim = null,
    row_label_callback = null,
    col_label_callback = null,
    col_dendro_callback = null,
    fetchOptions = {},
  } = {}
) => {
  if ([given_network, url, base_url].filter(Boolean).length !== 1) {
    throw new Error(
      '[clustergram] Pass exactly one of network, url (Matrix Zarr), or base_url (DegaFiles).'
    );
  }
  const network =
    given_network ??
    (url
      ? await network_from_zarr(url, { fetchOptions })
      : await networkFromDegaFiles(base_url, name, fetchOptions));
  const model = static_matrix_model(network, {
    viz_mode: viz_mode ?? (network.size_mat ? 'dotplot' : 'heatmap'),
    rank_dim,
  });
  const viz = await matrix_viz(
    model,
    el,
    network,
    width,
    height,
    row_label_callback,
    col_label_callback,
    col_dendro_callback
  );
  viz.model = model;
  return viz;
};

/**
 * Load and render a Clustergram from DegaFiles. Same as
 * `clustergram(el, { base_url, name, ... })`.
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
const matrix_from_dega_files = (
  el,
  base_url,
  name = 'default',
  width = 500,
  height = 500,
  row_label_callback = null,
  col_label_callback = null,
  col_dendro_callback = null,
  options = {}
) =>
  clustergram(el, {
    base_url,
    name,
    width,
    height,
    viz_mode: 'heatmap',
    row_label_callback,
    col_label_callback,
    col_dendro_callback,
    fetchOptions: options,
  });

/**
 * Load and render a Clustergram from a clustered Matrix Zarr store, written in
 * Python with `Matrix.write_zarr` (experimental). Same as
 * `clustergram(el, { url, ... })`.
 *
 * @param {HTMLElement} el - Container element for the visualization
 * @param {object} options - `url` and the other `clustergram` options
 * @returns {Promise<object>} - The matrix visualization object
 */
const matrix_from_zarr = (el, options = {}) => clustergram(el, options);

export default {
  // Options-object entry points for web pages without Python.
  landscape,
  clustergram,
  link_models,
  // Lower-level renderers and readers.
  anndata_zarr_source,
  landmark,
  landscape_ist,
  landscape_h_e,
  matrix_viz,
  matrix_from_dega_files,
  matrix_from_zarr,
  networkFromDegaFiles,
  network_from_dega_files: networkFromDegaFiles,
  network_from_zarr,
  yearbook,
  render,
  render_landmark,
  render_landscape_ist,
  render_landscape_h_e,
  render_landscape,
  render_yearbook,
  render_matrix_new,
  render_enrich,
  buildRowAxisSlice,
  buildColAxisSlice,
  buildCellSlice,
  emitMatrixSliceRequest,
};
