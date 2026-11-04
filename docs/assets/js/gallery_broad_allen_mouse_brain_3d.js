import celldega from './celldega.js';

const SOURCES = {
  zarr: {
    label: 'AnnData Zarr',
    options: {
      zarr_url:
        'https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/f76a3fa95ed9af8b6e96484a720cf4cbedc31819/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr',
    },
  },
  degafiles: {
    label: 'compact DegaFiles',
    options: {
      base_url:
        'https://raw.githubusercontent.com/cornhundred/celldega_xenium_E15.5_cell_cloud/8d3cd06fc1a478f386826c27ba0e900b40703a3a/xenium_E15.5_cell_cloud_compact',
    },
  },
};

let active = null;

function disposeMouseBrainCloud() {
  if (!active) return;
  active.disposed = true;
  active.selector?.removeEventListener('change', active.onChange);
  active.viz?.finalize?.();
  active.root.replaceChildren();
  active = null;
}

async function loadMouseBrainSource(state) {
  const source = SOURCES[state.selector?.value] || SOURCES.degafiles;
  const request = ++state.request;
  state.selector?.setAttribute('disabled', '');
  state.root.setAttribute('aria-busy', 'true');
  if (state.status) {
    state.status.hidden = false;
    state.status.textContent = `Loading 3.8 million cells from ${source.label}…`;
  }
  state.viz?.finalize?.();
  state.viz = null;
  state.root.replaceChildren();

  try {
    const viz = await celldega.landscape(state.root, {
      technology: 'point-cloud',
      manifest_name: 'cell_cloud.json',
      ...source.options,
      alignment: 'neighborhood',
      cluster_attr: 'leiden_1.0',
      use_adata_3d_centroids: false,
      ini_zoom: -3.05,
      rotation_orbit: -25,
      rotation_x: 20,
      height: 700,
      cell_size: 10,
    });
    // Navigation can remove this container while its data is still loading.
    if (state.disposed || state.request !== request) {
      viz?.finalize?.();
      return;
    }
    state.viz = viz;
    if (state.status) state.status.hidden = true;
  } catch (error) {
    if (state.disposed || state.request !== request) return;
    if (state.status) {
      state.status.textContent = `${source.label} could not load. Try the other data source or reload this page.`;
    }
    console.error(`Unable to load the 3D mouse brain from ${source.label}`, error);
  } finally {
    if (!state.disposed && state.request === request) {
      state.selector?.removeAttribute('disabled');
      state.root.setAttribute('aria-busy', 'false');
    }
  }
}

function initializeMouseBrainCloud() {
  const root = document.getElementById('cell-cloud-broad-allen');
  if (root && active?.root === root && !active.disposed) return;
  disposeMouseBrainCloud();
  if (!root) return;

  const selector = document.getElementById('cell-cloud-broad-allen-source');
  const requestedSource = new URL(window.location.href).searchParams.get('source');
  if (selector && SOURCES[requestedSource]) selector.value = requestedSource;
  const state = {
    root,
    selector,
    status: document.getElementById('cell-cloud-broad-allen-status'),
    viz: null,
    request: 0,
    disposed: false,
  };
  state.onChange = () => loadMouseBrainSource(state);
  selector?.addEventListener('change', state.onChange);
  active = state;
  loadMouseBrainSource(state);
}

// The imported bundle initializes WebAssembly asynchronously, so the DOM may
// already be ready by the time this module runs.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeMouseBrainCloud);
} else {
  initializeMouseBrainCloud();
}
window.addEventListener('pagehide', disposeMouseBrainCloud);
window.addEventListener('pageshow', initializeMouseBrainCloud);
// Also handle Material's optional instant-navigation page swaps.
window.document$?.subscribe(initializeMouseBrainCloud);
