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
import { show_loading } from './ui/loading';
import { hold_custom_messages } from './utils/held_messages';
import { link_models, make_options_model } from './utils/options_model';
import { create_from_png } from './viz/from_png';
import { landmark } from './viz/landmark';
import { landscape_h_e } from './viz/landscape_h_e';
import { landscape_ist } from './viz/landscape_ist';
import { landscape_model_values } from './viz/landscape_options';
import { matrix_viz } from './viz/matrix_viz';
import { multi_matrix_viz } from './viz/multi_matrix_viz';
import { read_png, screenshot_png } from './viz/png';
import {
  consume_initial_snapshot,
  handle_snapshot_message,
} from './viz/snapshot';
import { yearbook } from './viz/yearbook';
import { render_clerk } from './widgets/clerk_widget';
import { render_enrich } from './widgets/enrich_widget';
import { render_stack_switch, stack } from './widgets/stack_switch';

// Show the loading placeholder only for renders slower than this.
const LOADING_DELAY_MS = 150;

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
      technology: model.get('technology') || 'Chromium',
      alignment: model.get('alignment') || '',
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
    if (
      meta_cell_data.attr.length === 0 &&
      !single_cell_source.cell_categories
    ) {
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
    landscape_state =
      landscape_state === 'xy' || !Object.keys(umap_data).length
        ? 'xy'
        : 'umap';
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

/**
 * Viz API messages from Python for a spatial view (Landscape, CellCloud,
 * NeighborhoodCloud): screenshots, state snapshots and setters, answered with
 * one-off messages so nothing is saved into the notebook's widget state.
 */
const listen_for_viz_api = (model, landscape, element) => {
  // Raster capture: Python sends {event: 'capture_raster'}; reply with a one-off
  // message rather than synced traits, so captured images are never saved into the
  // notebook's widget state.
  if (!landscape || typeof landscape.capture_raster !== 'function') return;
  const on_capture_request = (msg) => {
    if (msg?.event !== 'capture_raster') return;
    try {
      const capture = landscape.capture_raster({
        max_size: msg.max_size,
        thumb_size: msg.thumb_size,
      });
      if (capture) {
        model.send({ event: 'raster', id: msg.id, ...capture });
      } else {
        model.send({
          event: 'raster_error',
          id: msg.id,
          error: 'No canvas to capture',
        });
      }
    } catch (e) {
      model.send({ event: 'raster_error', id: msg.id, error: e.message });
      handleValidationWarning('Raster capture failed', {
        data: { error: e.message },
      });
    }
  };
  model.on('msg:custom', on_capture_request);

  // Viz API for Python (e.g. Clerk): state snapshots and setters, answered with
  // one-off messages so nothing is saved into the notebook's widget state.
  const on_state_message = async (msg) => {
    if (
      landscape.snapshot &&
      ['capture_snapshot', 'restore_snapshot'].includes(msg?.event)
    ) {
      await handle_snapshot_message(model, landscape, msg);
      return;
    }
    if (msg?.event === 'get_state' && landscape.get_state) {
      try {
        const state = landscape.get_state(msg.options || {});
        model.send({ event: 'state', id: msg.id, state });
      } catch (e) {
        model.send({ event: 'state_error', id: msg.id, error: e.message });
      }
    } else if (msg?.event === 'apply_state' && landscape.apply_state) {
      try {
        const done = await landscape.apply_state(msg.changes || {});
        model.send({ event: 'applied', id: msg.id, done });
      } catch (e) {
        model.send({ event: 'apply_error', id: msg.id, error: e.message });
      }
    }
  };
  model.on('msg:custom', on_state_message);
  void consume_initial_snapshot(model, landscape, element);

  const finalize_landscape = landscape.finalize;
  landscape.finalize = () => {
    model.off?.('msg:custom', on_capture_request);
    model.off?.('msg:custom', on_state_message);
    finalize_landscape?.();
  };
};

const render_landscape = async ({ model, el }) => {
  const technology = model.get('technology');

  let landscape;
  if (
    ['MERSCOPE', 'Xenium', 'Chromium', 'Visium-HD'].includes(technology) ||
    is_orbit_technology(technology)
  ) {
    landscape = await render_landscape_ist({ model, el });
  } else if (['h&e'].includes(technology)) {
    landscape = await render_landscape_h_e({ model, el });
  }

  listen_for_viz_api(model, landscape, el);

  return landscape;
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

// One matrix of a Clustergram with several (Python's `matrices` trait), read
// from its parquet bytes when it is first shown.
const parquet_matrix_entry = (entry) => ({
  name: String(entry.name),
  description: entry.description || '',
  viz_mode: entry.viz_mode || '',
  row_entity: entry.row_entity || '',
  col_entity: entry.col_entity || '',
  load: () =>
    networkFromParquet(
      entry.meta || {},
      entry.mat,
      entry.row_nodes,
      entry.col_nodes,
      entry.row_linkage,
      entry.col_linkage,
      entry.dot_mat
    ),
});

const render_matrix_new = async ({ model, el }) => {
  // let network = model.get('network');
  let network;
  const width = model.get('width');
  const height = model.get('height');

  // Several matrices (Clustergram(matrix={name: Matrix})): the dropdown switches.
  const matrices = model.get('matrices') || [];
  if (matrices.length > 1) {
    return multi_matrix_viz(
      model,
      el,
      matrices.map(parquet_matrix_entry),
      width,
      height
    );
  }

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
async function render({ model: widget_model, el }) {
  // Requests Python sends while this view renders (e.g. apply_state run right after
  // the cell that displays it) are held, then delivered once it has rendered.
  const messages = hold_custom_messages(widget_model);
  const { model } = messages;
  let cleanup = null;
  let finalized = false;

  const finalize = () => {
    if (finalized) return;
    finalized = true;
    messages.close();

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

    // Widgets can take a while to fetch their data: show the awning mark and
    // "Loading…" until they appear (only if it takes more than a moment, so
    // panels that render at once don't flash it).
    const with_loading = async (render_widget) => {
      const remove = show_loading(el, {
        height: model.get('height'),
        delay: LOADING_DELAY_MS,
      });
      try {
        return await render_widget({ model, el });
      } finally {
        remove();
      }
    };

    switch (componentType) {
      case 'Landscape':
        cleanup = await with_loading(render_landscape);
        break;
      case 'CellCloud':
      case 'NeighborhoodCloud':
        // 3D-orbit widgets reuse the ist render path; the orbit view, layers,
        // and manifest filename are driven by the model's technology /
        // manifest_name traits (see render_landscape_ist and landscape_ist).
        cleanup = await with_loading(render_landscape_ist);
        listen_for_viz_api(model, cleanup, el);
        break;
      case 'Yearbook':
        cleanup = await with_loading(render_yearbook);
        break;
      case 'Matrix':
        cleanup = await with_loading(render_matrix_new);
        break;
      case 'Enrich':
        cleanup = await with_loading(render_enrich);
        break;
      case 'Clerk':
        cleanup = await with_loading(render_clerk);
        break;
      case 'StackSwitch':
        cleanup = render_stack_switch({ model, el });
        break;
      case 'Landmark':
        cleanup = await with_loading(render_landmark);
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
    // Every handler is listening now: deliver what arrived while rendering.
    messages.open();

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

// The model values that show saved manual categories: each labeled axis turned on
// with its (first) attribute, as Python's Clustergram.set_categories leaves them.
const manual_category_values = (manual_cat) => {
  let manual = manual_cat || {};
  if (typeof manual === 'string') {
    try {
      manual = JSON.parse(manual || '{}');
    } catch {
      manual = {};
    }
  }
  const attribute = (axis) =>
    Object.keys(manual?.[axis] || {}).find((name) => name) || '';
  const [row, col] = [attribute('row'), attribute('col')];
  return {
    manual_cat: JSON.stringify(manual),
    manual_row_cat: row,
    manual_col_cat: col,
    manual_cat_config: JSON.stringify({
      row: row ? { attribute: row } : null,
      col: col ? { attribute: col } : null,
    }),
  };
};

// The widget model a Clustergram renders with when there is no Python kernel.
const static_matrix_model = (
  network,
  {
    viz_mode = null,
    rank_dim = null,
    url = '',
    base_url = '',
    name = 'default',
    data_revision = '',
    width = 500,
    height = 500,
    manual_cat = null,
  } = {}
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
    // Saved views record where the data came from and compare a declared revision.
    url,
    base_url,
    name,
    width,
    height,
    data_revision,
    // Saved labels (Python's Clustergram.manual_cat), drawn when it renders.
    ...manual_category_values(manual_cat),
  });

/**
 * Show the loading mark (the pulsing Celldega awning and a label) in `el` while a
 * web page's visualization loads, as notebook widgets do, and remove it once the
 * visualization is drawn or fails. It appears only if loading takes more than a
 * moment, so a view that renders at once never flashes it.
 *
 * @param {HTMLElement} el - The visualization's container
 * @param {{loading?: boolean, loading_label?: string, height?: number}} options -
 *   `loading: false` turns the mark off; `loading_label` replaces "Loading…"
 *   (e.g. "Loading 3.8 million cells…"); `height` (px) is the space it takes.
 * @param {() => Promise<object>} draw - Loads and draws the visualization
 */
const while_loading = async (el, options, draw) => {
  const { loading = true, loading_label, height } = options || {};
  const remove =
    loading && el
      ? show_loading(el, {
          height: Number(height) || undefined,
          label: loading_label || 'Loading…',
          delay: LOADING_DELAY_MS,
        })
      : () => {};
  try {
    return await draw();
  } finally {
    remove();
  }
};

// The positional renderers (landscape_ist, yearbook) take `height` 12th.
const with_loading_mark =
  (draw_with) =>
  async (...args) =>
    while_loading(args[0], { height: args[11] }, () => draw_with(...args));

/**
 * Render a Landscape in a web page, without Python. The options are the
 * Python `Landscape`'s arguments, with the same defaults; for example a
 * single-cell AnnData Zarr store:
 * `await landscape(el, { zarr_url, cluster_attr: 'leiden', ini_zoom: -4.5 })`.
 * The Celldega loading mark shows while it loads.
 *
 * @param {HTMLElement} el - Container element for the visualization
 * @param {object} options - e.g. `zarr_url` or `base_url`, `cluster_attr`,
 *   `cell_attr`, `technology`, `ini_x`, `ini_y`, `ini_zoom`, `height`, `width`;
 *   `pins` (points of interest, Python's `landscape.pin_data`) and `show_pins`;
 *   `loading_label` (replaces "Loading…") or `loading: false` (no loading mark)
 * @returns {Promise<object>} The Landscape, with its `model` (see link_models)
 *   and `finalize()`. `model.set('show_pins', true)` shows its pins, as clicking
 *   PINS does.
 */
const landscape = async (el, options = {}) => {
  const { loading, loading_label, ...rest } = options;
  const model = make_options_model(landscape_model_values(rest));
  const viz = await while_loading(
    el,
    { loading, loading_label, height: model.get('height') },
    () => render_landscape_ist({ model, el })
  );
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
 * @param {string} [options.data_revision] - An immutable revision of the data
 *   (a release tag, commit hash or content digest). Saved views record it, and
 *   restoring a view declared for another revision is refused.
 * @param {object|string} [options.manual_cat] - Row and column labels to show
 *   (Python's `Clustergram.manual_cat`, e.g. a saved Clerk case's
 *   `clustergram_categories`): `{axis: {attribute: {values, colors}}}`
 * @param {function} [options.row_label_callback] - Called with a clicked row name
 * @param {function} [options.col_label_callback] - Called with a clicked column name
 * @param {function} [options.col_dendro_callback] - Called on dendrogram selections
 * @param {object} [options.fetchOptions] - Options for every fetch, e.g. headers
 * @param {string} [options.loading_label] - Replaces "Loading…" under the loading
 *   mark shown while it loads
 * @param {boolean} [options.loading=true] - Show the loading mark
 * @param {Array<object>} [options.matrices] - Several matrices about the same
 *   objects, switched with a dropdown, in place of `network`/`url`/`base_url`:
 *   each `{name, url}` (a Matrix Zarr store), `{name, network}` or `{name,
 *   base_url, dega_name}`, optionally with `description` (shown on hover) and
 *   `viz_mode`. Like Python's `Clustergram(matrix={name: Matrix})`.
 * @param {string} [options.active_matrix] - With `matrices`, the one shown first
 * @returns {Promise<object>} The Clustergram, with its `model` (see
 *   link_models) and `finalize()`; with `matrices`, also `switch_matrix(name)`
 */
const clustergram = async (
  el,
  {
    network: given_network,
    url,
    base_url,
    matrices = null,
    active_matrix = '',
    name = 'default',
    width = 500,
    height = 500,
    viz_mode,
    rank_dim = null,
    data_revision = '',
    manual_cat = null,
    row_label_callback = null,
    col_label_callback = null,
    col_dendro_callback = null,
    fetchOptions = {},
    loading = true,
    loading_label,
  } = {}
) => {
  // The matrix plus its label and dendrogram margins.
  const mark = { loading, loading_label, height: Number(height) + 100 };
  if (matrices?.length) {
    if ([given_network, url, base_url].some(Boolean)) {
      throw new Error(
        '[clustergram] Pass matrices, or one of network, url or base_url.'
      );
    }
    return while_loading(el, mark, async () => {
      const entries = matrices.map((matrix, index) => ({
        name: String(matrix.name ?? `Matrix ${index + 1}`),
        description: matrix.description || '',
        viz_mode: matrix.viz_mode || '',
        url: matrix.url || '',
        load: async () => {
          if (matrix.network) return matrix.network;
          if (matrix.url)
            return network_from_zarr(matrix.url, { fetchOptions });
          return networkFromDegaFiles(
            matrix.base_url,
            matrix.dega_name ?? 'default',
            fetchOptions
          );
        },
      }));
      const names = entries.map((entry) => entry.name);
      const model = make_options_model({
        viz_mode: viz_mode ?? null,
        rank_dim,
        url: '',
        base_url: '',
        name,
        width,
        height,
        data_revision: String(data_revision || ''),
        active_matrix: names.includes(active_matrix) ? active_matrix : names[0],
        ...manual_category_values(manual_cat),
      });
      const viz = await multi_matrix_viz(model, el, entries, width, height, {
        row_label_callback,
        col_label_callback,
        col_dendro_callback,
      });
      viz.model = model;
      return viz;
    });
  }
  if ([given_network, url, base_url].filter(Boolean).length !== 1) {
    throw new Error(
      '[clustergram] Pass exactly one of network, url (Matrix Zarr), or base_url (DegaFiles).'
    );
  }
  return while_loading(el, mark, async () => {
    const network =
      given_network ??
      (url
        ? await network_from_zarr(url, { fetchOptions })
        : await networkFromDegaFiles(base_url, name, fetchOptions));
    const model = static_matrix_model(network, {
      viz_mode: viz_mode ?? (network.size_mat ? 'dotplot' : 'heatmap'),
      rank_dim,
      url: url || '',
      base_url: base_url || '',
      name,
      width,
      height,
      data_revision: String(data_revision || ''),
      manual_cat,
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
  });
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

/**
 * Render a saved Clerk conversation in a web page, without Python: a case saved
 * with the panel's Save button (`Clerk.save_conversation`). It's read-only: its
 * genes, clusters, cited views and screenshots change linked widgets, and asking
 * needs a notebook. Link it to a Landscape and Clustergram with `link_models`:
 * `link_models(clerk.model, 'landscape_request', ls.model, 'view_request')` and
 * `link_models(clerk.model, 'clustergram_request', cgm.model, 'view_request')`.
 * Pass the case's labels, `annotations.manual_cat` (`clustergram_categories` in
 * cases saved before 0.29.1), to `clustergram({manual_cat})` to show its cell
 * types. The `url` can be on any host that allows cross-origin reads, such as
 * Hugging Face.
 *
 * @param {HTMLElement} el - Container element for the panel
 * @param {object} options
 * @param {object} [options.conversation] - The saved conversation (parsed JSON)
 * @param {string} [options.url] - Or the URL of its JSON file
 * @param {number} [options.width=0] - Width in px; 0 fills the container
 * @param {number} [options.height=600] - Height in px
 * @param {object} [options.fetchOptions] - Options for fetching `url`
 * @param {string} [options.loading_label] - Replaces "Loading…" under the loading
 *   mark shown while it loads
 * @param {boolean} [options.loading=true] - Show the loading mark
 * @returns {Promise<object>} The panel, with its `model`, the `conversation`,
 *   and `finalize()`
 */
const clerk = async (
  el,
  {
    conversation,
    url,
    width = 0,
    height = 600,
    fetchOptions = {},
    loading = true,
    loading_label,
  } = {}
) => {
  if (!conversation === !url) {
    throw new Error('[clerk] Pass a conversation or its url.');
  }
  return while_loading(el, { loading, loading_label, height }, async () => {
    let saved = conversation;
    if (!saved) {
      const response = await fetch(url, fetchOptions);
      if (!response.ok) {
        throw new Error(`[clerk] Couldn't load ${url} (${response.status})`);
      }
      saved = await response.json();
    }
    if (!Array.isArray(saved?.messages)) {
      throw new Error('[clerk] Not a saved Clerk conversation');
    }
    const model = make_options_model({
      width,
      height,
      messages: saved.messages,
      cluster_names: saved.cluster_names || [],
      cluster_labels: saved.cluster_labels || {},
      context_info: saved.context_info || '',
      model: saved.model || '',
      effort: saved.effort || '',
      gene_list: [],
      pending: false,
      can_restore: false,
      fetch_enrichr: false,
      briefing_label: '',
    });
    const viz = await render_clerk({ model, el });
    return { ...viz, model, conversation: saved };
  });
};

const from_png = create_from_png({ landscape, clustergram });

export default {
  clerk,
  // Options-object entry points for web pages without Python.
  landscape,
  clustergram,
  // Several visualizations in one place, one shown at a time.
  stack,
  link_models,
  read_png,
  snapshot_png: screenshot_png,
  screenshot_png,
  from_png,
  // Lower-level renderers and readers.
  anndata_zarr_source,
  landmark,
  landscape_ist: with_loading_mark(landscape_ist),
  landscape_h_e,
  matrix_viz,
  multi_matrix_viz,
  matrix_from_dega_files,
  matrix_from_zarr,
  networkFromDegaFiles,
  network_from_dega_files: networkFromDegaFiles,
  network_from_zarr,
  yearbook: with_loading_mark(yearbook),
  render,
  render_landmark,
  render_landscape_ist,
  render_landscape_h_e,
  render_landscape,
  render_yearbook,
  render_matrix_new,
  render_enrich,
  render_clerk,
  buildRowAxisSlice,
  buildColAxisSlice,
  buildCellSlice,
  emitMatrixSliceRequest,
};
