import './widget.css';
import { landscape_h_e } from './viz/landscape_h_e';
import { landscape_ist } from './viz/landscape_ist';
import { landscape_sst } from './viz/landscape_sst';
import { matrix_viz } from './viz/matrix_viz';

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
  const meta_cell = model.get('meta_cell');
  const meta_cluster = model.get('meta_cluster');
  const umap = model.get('umap');
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
    meta_cell,
    meta_cluster,
    umap,
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

const render_landscape = async ({ model, el }) => {
  const technology = model.get('technology');

  if (['MERSCOPE', 'Xenium'].includes(technology)) {
    return render_landscape_ist({ model, el });
  } else if (['Visium-HD'].includes(technology)) {
    return render_landscape_sst({ model, el });
  } else if (['h&e'].includes(technology)) {
    return render_landscape_h_e({ model, el });
  }
};

const render_matrix_new = async ({ model, el }) => {
  const network = model.get('network');
  const width = model.get('width');
  const height = model.get('height');

  matrix_viz(model, el, network, width, height);
};

// Main render function - no export keyword
function render({ model, el }) {
  try {
    const componentType = model.get('component');

    // Add null/undefined checks
    if (!componentType) {
      console.error('Component type is not defined');
      return;
    }

    switch (componentType) {
      case 'Landscape':
        return render_landscape({ model, el });
      case 'Matrix':
        return render_matrix_new({ model, el });
      default:
        console.error(`Unknown component type: ${componentType}`);
        return;
    }
  } catch (error) {
    console.error('Error in render function:', error);
    // Create error display in the element
    el.innerHTML = `<div style="color: red; padding: 10px;">Error: ${error.message}</div>`;
  }
}

export default {
  render,
  render_landscape_ist,
  render_landscape_sst,
  render_landscape_h_e,
  render_landscape,
  render_matrix_new,
};
