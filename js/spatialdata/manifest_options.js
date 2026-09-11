/**
 * Read the SpatialData-native settings out of `landscape_parameters.json`.
 *
 * The manifest stays: it is what tells the viewer where the store is and which columns to
 * use, and it keeps DegaFiles working unchanged. A manifest without a `spatialdata` block
 * means "read everything from Parquet as before", so this is opt-in by absence.
 *
 * Expected shape:
 *
 *   "spatialdata": {
 *     "store_url":      "../..",      // relative to base_url, or absolute
 *     "table":          "table",
 *     "cluster_column": "cell_type",  // optional obs column
 *     "centroid_key":   "spatial",    // optional obsm key
 *     "native": ["metadata", "cbg"],  // which components to read from Zarr
 *     "image_element": "morphology_focus"
 *   }
 */

/** Components that may be served natively; anything absent falls back to Parquet. */
export const NATIVE_COMPONENTS = ['metadata', 'cbg', 'images'];

/**
 * Resolve a possibly relative store URL against the profile's base URL.
 * `base_url` points at the profile directory, the store root is usually two levels up.
 */
export const resolveStoreUrl = (baseUrl, storeUrl) => {
  if (!storeUrl) return null;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(storeUrl))
    return storeUrl.replace(/\/+$/, '');

  const base = String(baseUrl).replace(/\/+$/, '');
  const segments = base.split('/');
  for (const part of String(storeUrl).split('/')) {
    if (part === '' || part === '.') continue;
    if (part === '..') {
      // Never pop past the origin -- "https://host" must keep its two empty segments.
      if (segments.length > 3) segments.pop();
    } else {
      segments.push(part);
    }
  }
  return segments.join('/');
};

/**
 * @returns {null | {storeUrl, table, clusterColumn, centroidKey, native: Set<string>}}
 */
export const spatialDataOptionsFromManifest = (manifest, baseUrl) => {
  const block = manifest?.spatialdata;
  if (!block) return null;

  const storeUrl = resolveStoreUrl(baseUrl, block.store_url ?? '../..');
  if (!storeUrl) return null;

  const requested = Array.isArray(block.native)
    ? block.native
    : NATIVE_COMPONENTS;

  return {
    storeUrl,
    table: block.table ?? 'table',
    clusterColumn: block.cluster_column ?? null,
    centroidKey: block.centroid_key ?? 'spatial',
    imageElement:
      block.image_element ?? manifest?.source?.image_element ?? null,
    // Centroids in obsm are in the annotating element's units. The shapes element carries
    // the transform into the display coordinate system, and the profile manifest already
    // records which element that is.
    transformElement:
      block.transform_element ??
      (manifest?.source?.shapes_element
        ? `shapes/${manifest.source.shapes_element}`
        : null),
    coordinateSystem:
      block.coordinate_system ??
      manifest?.source?.coordinate_system ??
      'global',
    native: new Set(requested.filter((c) => NATIVE_COMPONENTS.includes(c))),
    // `feature_code` indexes genes-then-controls, but `var` holds only the genes. Xenium
    // pancreas reaches code 539 against 377 genes, so without the control names those
    // transcripts index past the end of the colour table and silently lose their colour.
    featureCatalog: manifest?.feature_catalog ?? null,
  };
};
