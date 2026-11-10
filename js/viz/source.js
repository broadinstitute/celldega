// Constructor inputs that describe data and rendering, never credentials,
// callbacks, widget messages or large in-memory scientific payloads.
export const SOURCE_OPTIONS = {
  clustergram: ['url', 'base_url', 'name', 'width', 'height', 'viz_mode', 'rank_dim', 'data_revision'],
  landscape: [
    'base_url', 'base_urls', 'zarr_url', 'zarr_layer', 'technology',
    'cluster_attr', 'cell_attr', 'alignment', 'segmentation', 'dataset_name',
    'cell_name_prefix', 'manifest_name', 'centroids_url', 'gene_signature_url',
    'width', 'height', 'ini_x', 'ini_y', 'ini_z', 'ini_zoom',
    'rotation_orbit', 'rotation_x', 'rotate', 'cell_size',
    'scale_bar_microns_per_pixel', 'max_tiles_to_view', 'min_zoom', 'max_zoom',
    'intermediate_zoom_limit', 'nbhd_edit', 'use_adata_3d_centroids', 'data_revision',
  ],
};

export const source_options = (values, kind) => Object.fromEntries(
  SOURCE_OPTIONS[kind].filter((key) => values[key] !== undefined && values[key] !== null)
    .map((key) => [key, values[key]])
);

export const model_source = (model, kind, dimensions = {}) => {
  const values = Object.fromEntries(SOURCE_OPTIONS[kind].map((key) => [key, model?.get?.(key)]));
  const options = source_options({ ...values, ...dimensions }, kind);
  const widget = kind === 'clustergram' ? 'Clustergram'
    : options.technology === 'point-cloud' ? 'CellCloud'
      : options.technology === 'neighborhood-cloud' ? 'NeighborhoodCloud' : 'Landscape';
  const in_memory = kind === 'landscape' && ['meta_cell_parquet', 'meta_cluster_parquet', 'umap_parquet', 'centroids_parquet']
    .some((key) => model?.get?.(key)?.byteLength > 0);
  const has_source = kind === 'clustergram'
    ? Boolean(options.url || options.base_url)
    : Boolean(options.zarr_url || options.base_url || options.base_urls?.length);
  return { widget, options, requires_data: !has_source || in_memory };
};
