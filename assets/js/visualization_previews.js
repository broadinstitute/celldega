import celldega from './celldega.js';

// Small interactive previews at the top of the visualization guides. Each runs
// only on the page that contains its element.

const ATERA_KIDNEY =
  'https://raw.githubusercontent.com/broadinstitute/' +
  'Celldega_Atera_v1_WTA_Kidney_non_diseased_FFPE/' +
  '3a46ab4db67821eef3b8ff8d1c3704fb7b3bb48f';

const TABULA_SAPIENS =
  'https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/' +
  'resolve/main/Tabula_Sapiens';

const THICK_MERFISH =
  'https://raw.githubusercontent.com/broadinstitute/' +
  'scverse-owkin_thick_merfish/main/landscape_files';

const PREVIEWS = {
  // The whole kidney section; zoom in for glomeruli, tubules, and transcripts.
  'preview-landscape': (el) =>
    celldega.landscape(el, {
      base_url: ATERA_KIDNEY,
      ini_x: 28322,
      ini_y: 16570,
      ini_zoom: -6.5,
      height: 450,
    }),

  // Kidney cells with the highest expression of the podocyte marker NPHS2.
  'preview-yearbook': (el) =>
    celldega.yearbook(
      el,
      {},
      '',
      ATERA_KIDNEY,
      'Atera kidney',
      [],
      2, // rows
      4, // columns
      50, // portrait width in microns
      4, // gap between portraits
      0, // full width
      450,
      {},
      [],
      {},
      [],
      'default',
      {},
      null,
      0,
      { gene: 'NPHS2', max_cells: 64 }
    ),

  // Thick-tissue MERFISH, tilted to show its depth.
  'preview-cell-cloud': (el) =>
    celldega.landscape(el, {
      technology: 'point-cloud',
      manifest_name: 'landscape_parameters.json',
      base_url: THICK_MERFISH,
      cell_size: 10,
      ini_x: 1461,
      ini_y: 1196,
      ini_z: 50,
      ini_zoom: -2.3,
      rotation_x: 45,
      rotation_orbit: -30,
      height: 450,
    }),

  // Top marker genes of Tabula Sapiens cell types, as a dot plot.
  'preview-clustergram': (el) =>
    celldega.clustergram(el, {
      url: `${TABULA_SAPIENS}/tabula_sapiens_cell_type_markers.zarr`,
      width: 520,
      height: 450,
      viz_mode: 'dotplot',
      rank_dim: 3,
    }),
};

document.addEventListener('DOMContentLoaded', async () => {
  for (const [id, render] of Object.entries(PREVIEWS)) {
    const el = document.getElementById(id);
    if (!el) continue;
    const status = el.parentElement.querySelector('.viz-preview-status');
    try {
      await render(el);
      if (status) status.hidden = true;
    } catch (error) {
      if (status) {
        status.textContent = 'The preview could not load. Please reload to try again.';
      }
      console.error(`Unable to load ${id}`, error);
    }
  }
});
