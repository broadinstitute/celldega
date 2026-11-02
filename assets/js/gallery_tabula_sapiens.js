import celldega from './celldega.js';

const DATA =
  'https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/main/Tabula_Sapiens';

async function initializeTabulaGallery() {
  const root = document.querySelector('[data-tabula-gallery]');
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = 'true';
  const linked = root.dataset.tabulaGallery === 'linked';

  // Keep either component usable if the other fails to load.
  const load = async (name, render) => {
    const status = root.querySelector(`[data-tabula-status="${name}"]`);
    try {
      const viz = await render();
      status.hidden = true;
      return viz;
    } catch (error) {
      status.textContent = `The ${name === 'landscape' ? 'atlas' : 'Clustergram'} could not load. Reload this page to try again.`;
      console.error(`Unable to load Tabula Sapiens ${name}`, error);
      return null;
    }
  };
  const [landscape, clustergram] = await Promise.all([
    load('landscape', () =>
      celldega.landscape(root.querySelector('[data-tabula-landscape]'), {
        zarr_url: `${DATA}/tabula_sapiens.zarr`,
        zarr_layer: 'log1p_csc',
        gene_signature_url: `${DATA}/tabula_sapiens_cell_type_signatures.zarr`,
        cell_attr: ['cell_type', 'tissue_in_publication', 'compartment'],
        cluster_attr: 'cell_type',
        landscape_state: 'umap',
        dataset_name: 'Tabula Sapiens · All Cells',
        // The 550px Clustergram adds a 100px canvas margin; both have toolbars.
        height: linked ? 650 : 750,
        ini_zoom: linked ? -4.6 : -4.3,
        ini_x: 5000,
        ini_y: 5000,
      })
    ),
    linked
      ? load('clustergram', () =>
          celldega.clustergram(root.querySelector('[data-tabula-clustergram]'), {
            url: `${DATA}/tabula_sapiens_cell_type_markers.zarr`,
            width: 550,
            height: 550,
            viz_mode: 'dotplot',
            rank_dim: 3,
          })
        )
      : Promise.resolve(null),
  ]);
  if (landscape && clustergram) {
    celldega.link_models(
      clustergram.model,
      'click_info',
      landscape.model,
      'update_trigger'
    );
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeTabulaGallery);
} else {
  initializeTabulaGallery();
}
