// The Python Landscape widget's synced defaults, so `landscape(el, options)`
// in a plain web page behaves like `Landscape(...)` in a notebook.
export const LANDSCAPE_DEFAULTS = {
  alignment: '',
  base_url: '',
  base_urls: [],
  cell_attr: ['leiden'],
  cell_clusters: {},
  cell_name_prefix: false,
  centroids_url: '',
  cluster_attr: 'leiden',
  creds: {},
  dataset_name: '',
  focused_gene: '',
  gates: { type: 'FeatureCollection', features: [] },
  height: 600,
  ini_x: 0,
  ini_y: 0,
  ini_z: 0,
  ini_zoom: 0,
  intermediate_zoom_limit: 9,
  landscape_state: 'spatial',
  max_tiles_to_view: 50,
  max_zoom: null,
  meta_cluster: {},
  min_zoom: null,
  nbhd_edit: false,
  nbhd_geojson: {},
  region: {},
  rotate: 0,
  rotation_orbit: 0,
  rotation_x: 0,
  scale_bar_microns_per_pixel: null,
  segmentation: 'default',
  selected_cells: [],
  token: '',
  update_trigger: {},
  use_adata_3d_centroids: true,
  view_space: {},
  width: 0,
  xy_genes: [],
  xy_scale: 'log1p',
  zarr_layer: '',
  zarr_url: '',
};

/**
 * Model values for `landscape(el, options)`, following the Python widget:
 * a `zarr_url` defaults to the Chromium technology and excludes `base_url`,
 * and `cluster_attr` is always one of the cell attributes.
 *
 * @param {object} options - Python Landscape arguments, e.g. `zarr_url`,
 *   `base_url`, `cluster_attr`, `cell_attr`, `ini_zoom`, `height`.
 * @returns {object} Values for a widget model.
 */
export const landscape_model_values = (options = {}) => {
  const { zarr_url, base_url, base_urls } = options;
  if (zarr_url && (base_url || base_urls?.length)) {
    throw new Error(
      '[landscape] Pass either base_url (DegaFiles) or zarr_url (AnnData Zarr), not both.'
    );
  }
  const technology = options.technology ?? (zarr_url ? 'Chromium' : 'Xenium');
  if (zarr_url && technology !== 'Chromium') {
    throw new Error(
      "[landscape] zarr_url supports technology='Chromium' only."
    );
  }
  const cluster_attr = options.cluster_attr ?? LANDSCAPE_DEFAULTS.cluster_attr;
  const cell_attr = options.cell_attr ?? LANDSCAPE_DEFAULTS.cell_attr;
  return {
    ...LANDSCAPE_DEFAULTS,
    ...options,
    technology,
    cluster_attr,
    cell_attr: [...new Set([...cell_attr, cluster_attr])],
  };
};
