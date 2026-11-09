import celldega from './celldega.js';

// Atera v1 WTA fresh frozen sections: DegaFiles for the Landscape and a clustered
// Matrix of the default Leiden clusters for the Clustergram. Landscape tiles come
// from GitHub; the Clustergram AnnData-Zarr stores remain on Hugging Face.
const MATRIX_DATA =
  'https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/main/Atera';

// The view opens on the whole section (image centre, zoomed to fit).
const SAMPLES = {
  hippocampus: {
    name: 'Atera_v1_WTA_S4A_Brain_Hippocampus_ND_FF',
    repository: 'celldega_atera-wta-ff-human-nd-brain',
    dataset_name: 'Atera brain hippocampus (non-diseased, FF)',
    ini_x: 30684,
    ini_y: 21274,
    ini_zoom: -6.7,
  },
  colorectal: {
    name: 'Atera_v1_WTA_S4B_Colorectal_Cancer_FF',
    repository: 'celldega_atera-wta-ff-human-crc',
    dataset_name: 'Atera colorectal cancer (FF)',
    ini_x: 30676,
    ini_y: 18918,
    ini_zoom: -6.7,
  },
  breast: {
    name: 'Atera_v1_WTA_S4C_Breast_Cancer_FF',
    repository: 'celldega_atera-wta-ff-human-breast-cancer',
    dataset_name: 'Atera breast cancer (FF)',
    ini_x: 35367,
    ini_y: 18965,
    ini_zoom: -6.9,
  },
};

async function initializeAteraGallery() {
  const root = document.querySelector('[data-atera-gallery]');
  if (!root || root.dataset.initialized) return;
  const sample = SAMPLES[root.dataset.ateraGallery];
  if (!sample) return;
  root.dataset.initialized = 'true';
  const base_url = `https://raw.githubusercontent.com/broadinstitute/${sample.repository}/main`;
  const matrix_url = `${MATRIX_DATA}/${sample.name}/cgm/default_clusters.zarr`;

  // Keep either component usable if the other fails to load.
  const load = async (name, render) => {
    const status = root.querySelector(`[data-atera-status="${name}"]`);
    try {
      const viz = await render();
      status.hidden = true;
      return viz;
    } catch (error) {
      status.textContent = `The ${name === 'landscape' ? 'tissue view' : 'Clustergram'} could not load. Reload this page to try again.`;
      console.error(`Unable to load the ${sample.name} ${name}`, error);
      return null;
    }
  };
  const [landscape, clustergram] = await Promise.all([
    load('landscape', () =>
      celldega.landscape(root.querySelector('[data-atera-landscape]'), {
        base_url,
        technology: 'Xenium',
        dataset_name: sample.dataset_name,
        ini_x: sample.ini_x,
        ini_y: sample.ini_y,
        ini_zoom: sample.ini_zoom,
        height: 650,
      })
    ),
    load('clustergram', () =>
      celldega.clustergram(root.querySelector('[data-atera-clustergram]'), {
        url: matrix_url,
        width: 550,
        height: 550,
        viz_mode: 'dotplot',
        rank_dim: 3,
      })
    ),
  ]);
  if (landscape && clustergram) {
    // Clicking a gene colors the cells by it; clicking a cluster selects its cells.
    celldega.link_models(
      clustergram.model,
      'click_info',
      landscape.model,
      'update_trigger'
    );
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeAteraGallery);
} else {
  initializeAteraGallery();
}
