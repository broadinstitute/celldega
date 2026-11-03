import celldega from './celldega.js';

async function initializeMouseBrainCloud() {
  const root = document.getElementById('cell-cloud-broad-allen');
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = 'true';

  const status = document.getElementById('cell-cloud-broad-allen-status');
  try {
    await celldega.landscape(root, {
      technology: 'point-cloud',
      manifest_name: 'cell_cloud.json',
      base_url:
        'https://raw.githubusercontent.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/main/xenium_E15.5_cell_cloud',
      alignment: 'neighborhood',
      cluster_attr: 'leiden_1.0',
      use_adata_3d_centroids: false,
      ini_zoom: -3.05,
      rotation_orbit: -25,
      rotation_x: 20,
      height: 700,
      cell_size: 10,
    });
    status.hidden = true;
  } catch (error) {
    root.dataset.initialized = '';
    status.textContent =
      'The 3D mouse brain could not load. Reload this page to try again.';
    console.error('Unable to load the 3D mouse brain', error);
  }
}

// The imported bundle initializes WebAssembly asynchronously, so the DOM may
// already be ready by the time this module runs.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeMouseBrainCloud);
} else {
  initializeMouseBrainCloud();
}
