import celldega from './celldega.js';

// A saved Clerk case on the Atera kidney section, read in the browser without
// Python: the conversation (with the Clustergram's cell-type labels) and the
// clustered Matrix are copied into docs/assets/data/clerk_atera_kidney/ by
// notebooks/clerk/Clerk_Atera_Kidney_Reopen_Case.ipynb (git ignores them for now);
// the tissue streams from the DegaFiles on GitHub.
const DATA = new URL('../data/clerk_atera_kidney/', import.meta.url);
const BASE_URL =
  'https://raw.githubusercontent.com/broadinstitute/' +
  'Celldega_Atera_v1_WTA_Kidney_non_diseased_FFPE/' +
  '3a46ab4db67821eef3b8ff8d1c3704fb7b3bb48f';

async function initializeClerkGallery() {
  const root = document.querySelector('[data-clerk-gallery="atera-kidney"]');
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = 'true';

  const status = (name) => root.querySelector(`[data-clerk-status="${name}"]`);
  const fail = (name, what, error) => {
    status(name).hidden = false;
    status(name).textContent =
      `The ${what} could not load. Reload this page to try again.`;
    console.error(`Unable to load the Clerk gallery ${name}`, error);
  };

  let conversation;
  try {
    const response = await fetch(new URL('conversation.json', DATA));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    conversation = await response.json();
  } catch (error) {
    fail('clerk', 'Clerk conversation', error);
    return;
  }

  // Keep each component usable if another fails to load.
  const load = async (name, what, render) => {
    try {
      const viz = await render();
      status(name).hidden = true;
      return viz;
    } catch (error) {
      fail(name, what, error);
      return null;
    }
  };
  // The views first, then the conversation, so its links reach widgets that are
  // ready for them.
  const [landscape, clustergram] = await Promise.all([
    load('landscape', 'tissue view', () =>
      celldega.landscape(root.querySelector('[data-clerk-landscape]'), {
        base_url: BASE_URL,
        technology: 'Xenium',
        dataset_name: 'Atera kidney — default clusters',
        ini_x: 28322,
        ini_y: 16570,
        ini_zoom: -6.5,
        height: 650,
      })
    ),
    load('clustergram', 'Clustergram', () =>
      celldega.clustergram(root.querySelector('[data-clerk-clustergram]'), {
        url: new URL('kidney_leiden_markers.zarr', DATA).href,
        width: 400,
        height: 450,
        viz_mode: 'dotplot',
        rank_dim: 10,
        // The case's cell types (columns) and the marker genes behind them (rows),
        // as saved (annotations), or by Clerk before 0.29.1 (clustergram_categories).
        manual_cat:
          conversation.annotations?.manual_cat ??
          conversation.clustergram_categories,
      })
    ),
  ]);

  // Clustergram clicks color or select cells; clusters selected in the tissue
  // show as blue Clustergram columns.
  if (landscape && clustergram) {
    celldega.link_models(
      clustergram.model,
      'click_info',
      landscape.model,
      'update_trigger'
    );
    celldega.link_models(
      landscape.model,
      'selected_clusters',
      clustergram.model,
      'highlighted_cols'
    );
  }

  const clerk = await load('clerk', 'Clerk conversation', () =>
    celldega.clerk(root.querySelector('[data-clerk-panel]'), {
      conversation,
      height: 760,
    })
  );
  // The conversation's genes, clusters, cited views and screenshots change the
  // views it was about.
  if (clerk && landscape) {
    celldega.link_models(
      clerk.model,
      'landscape_request',
      landscape.model,
      'view_request'
    );
  }
  if (clerk && clustergram) {
    celldega.link_models(
      clerk.model,
      'clustergram_request',
      clustergram.model,
      'view_request'
    );
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeClerkGallery);
} else {
  initializeClerkGallery();
}
