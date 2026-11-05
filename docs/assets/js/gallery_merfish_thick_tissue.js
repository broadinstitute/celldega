import celldega from './celldega.js';

document.addEventListener('DOMContentLoaded', async () => {
  const element = document.getElementById('cell-cloud-thick-merfish');
  if (!element) return;
  const status = document.getElementById('cell-cloud-thick-merfish-status');

  try {
    await celldega.landscape(element, {
      technology: 'point-cloud',
      // These point-cloud DegaFiles predate cell_cloud.json.
      manifest_name: 'landscape_parameters.json',
      base_url:
        'https://raw.githubusercontent.com/broadinstitute/' +
        'scverse-owkin_thick_merfish/main/landscape_files',
      cell_size: 10,
      // Centered on the tissue slab, tilted to show its depth.
      ini_x: 1461,
      ini_y: 1196,
      ini_z: 50,
      ini_zoom: -2.3,
      rotation_x: 45,
      rotation_orbit: -30,
      height: 700,
    });
    if (status) status.hidden = true;
  } catch (error) {
    if (status) {
      status.textContent = 'The 3D view could not load. Please reload to try again.';
    }
    console.error('Unable to load the thick-tissue MERFISH gallery', error);
  }
});
