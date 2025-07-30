import './widget.css';

import { options, set_options } from './global_variables/fetch_options';
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
import { render_enrich } from './widgets/enrich_widget';

function issueCrossPlatformWarning(message, model, el, showInNotebook = true) {
  /* eslint-disable-next-line no-console */
  console.warn(`⚠️ ${message}`);

  if (showInNotebook) {
    const warnDiv = document.createElement('div');
    warnDiv.style.color = 'orange';
    warnDiv.style.padding = '6px';
    warnDiv.style.fontSize = '0.9em';
    warnDiv.style.fontWeight = 'bold';
    warnDiv.textContent = `⚠️ ${message}`;
    el.appendChild(warnDiv);
  }

  if (model?.send) {
    model.send({ event: 'js_warning', message });
  }
}

const fetchLandscapeTechnology = async (model, _el) => {
  const base_url = model.get('base_url');
  const token = model.get('token');

  try {
    set_options(token);
    const url = `${base_url}/landscape_parameters.json`;
    const response = await fetch(url, options.fetch);

    if (!response.ok) {
      const error = new Error(
        `Failed to fetch landscape_parameters.json: ${response.statusText}`
      );
      error.status = response.status;
      throw error;
    }

    const json = await response.json();

    if (!json.technology) {
      const message =
        'The landscape_parameters.json file appears to be missing the `technology` field. Please verify its contents.';

      /* eslint-disable-next-line no-console */
      console.warn(`⚠️ ${message}`);
      model.send({ event: 'js_error', message });
      throw new Error(message);
    }

    return json.technology;
  } catch (error) {
    const errorResult = handleAsyncError(error, {
      context: 'fetchLandscapeTechnology',
      messages: {
        notFound: 'landscape_parameters.json not found',
        unexpected: 'Error fetching landscape_parameters.json',
      },
    });

    model.send({ event: 'js_error', message: errorResult.message });
    return null;
  }
};

// Remove export keywords from render functions
const render_landscape_ist = async ({ model, el }) => {
  const token = model.get('token');
  const creds = model.get('creds');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const width = model.get('width');
  const height = model.get('height');

  const nbhd = model.get('nbhd_geojson');

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

  const landscape_state = model.get('landscape_state');
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
    {},
    nbhd,
    landscape_state,
    segmentation,
    creds
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

const DEFAULT_TECHNOLOGY = 'Xenium';

const render_landscape = async ({ model, el }) => {
  let technology = model.get('technology');
  const userPassedTechnology =
    Object.prototype.hasOwnProperty.call(model, 'attributes') &&
    Object.prototype.hasOwnProperty.call(model.attributes, 'technology');

  if (!technology) {
    issueCrossPlatformWarning(
      'Technology was not passed in the function – attempting to fetch this from landscape_parameters.json.',
      model,
      el,
      false
    );

    const fetchedTech = await fetchLandscapeTechnology(model, el);

    if (!fetchedTech) {
      // Fallback to DEFAULT_TECHNOLOGY with a strong warning
      const fallbackMsg =
        `Neither technology was explicitly passed nor found in landscape_parameters.json. ` +
        `Falling back to default: ${DEFAULT_TECHNOLOGY}`;
      issueCrossPlatformWarning(fallbackMsg, model, el);

      technology = DEFAULT_TECHNOLOGY;
    } else {
      technology = fetchedTech;
    }

    model.set('technology', technology);
    model.save_changes();
  } else if (userPassedTechnology) {
    issueCrossPlatformWarning(
      'Setting `technology` manually is deprecated and will be removed in a future release. Please rely on automatic detection via landscape_parameters.json.',
      model,
      el
    );
  }

  if (
    !['MERSCOPE', DEFAULT_TECHNOLOGY, 'Visium-HD', 'h&e'].includes(technology)
  ) {
    const msg = `Unsupported technology: ${technology}`;
    handleValidationWarning(msg);
    model.send({ event: 'js_warning', message: msg });
    return;
  }

  if (['MERSCOPE', DEFAULT_TECHNOLOGY].includes(technology)) {
    return render_landscape_ist({ model, el });
  } else if (technology === 'Visium-HD') {
    return render_landscape_sst({ model, el });
  } else if (technology === 'h&e') {
    return render_landscape_h_e({ model, el });
  }
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
      model.get('col_linkage_parquet')
    );
  }

  return matrix_viz(model, el, network, width, height);
};

// Main render function - no export keyword
async function render({ model, el }) {
  let cleanup = null;
  model.on('msg:custom', (msg) => {
    if (msg.event === 'py_warning') {
      /* eslint-disable-next-line no-console */
      console.warn('[PYTHON WARNING]', msg.message);
      el.innerHTML += `<div style="color: orange; padding: 5px;">⚠️ ${msg.message}</div>`;
    } else if (msg.event === 'py_error') {
      /* eslint-disable-next-line no-console */
      console.error('[PYTHON ERROR]', msg.message);
      el.innerHTML += `<div style="color: red; padding: 5px;">❌ ${msg.message}</div>`;
    }
  });

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

export default {
  landscape_ist,
  landscape_sst,
  landscape_h_e,
  matrix_viz,
  render,
  render_landscape_ist,
  render_landscape_sst,
  render_landscape_h_e,
  render_landscape,
  render_matrix_new,
  render_enrich,
};
