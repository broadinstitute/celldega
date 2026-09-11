import { options } from './fetch_options';

/**
 * Root Zarr attribute holding the profile when a store carries no manifest file.
 *
 * A SpatialData store can record everything a viewer needs in its own root attributes,
 * which means no `visualization/` directory has to exist.
 */
const ROOT_MANIFEST_KEY = 'spatial_tiling';

const celldegaParametersFromSpatialTiling = (manifest) => ({
  // Viewer policy belongs in this adapter rather than the generic storage profile.
  technology: manifest?.source?.technology ?? 'Xenium',
  use_row_groups: true,
  use_int_index: true,
  segmentation_approach: ['default'],
  image_info: [],
  image_format: '.webp',
  ...manifest,
 // Canonical spatial tiling stores grid geometry inside tile_grid.
 // Celldega's existing viewport code expects the legacy top-level field.
 tile_size: manifest?.tile_size ?? manifest?.tile_grid?.tile_size,
});

export const set_landscape_parameters = async (
  img,
  base_url,
  aws,
  manifest_name = 'landscape_parameters.json'
) => {
  const fetch_url = (url) => (aws ? aws.fetch(url) : fetch(url, options.fetch));
  const fetch_manifest = (name) => fetch_url(`${base_url}/${name}`);

  let response = await fetch_manifest(manifest_name);

  // Fall back to the legacy manifest name so DegaFiles built before the
  // cell_cloud.json / neighborhood_cloud.json rename still render.
  if (!response.ok && manifest_name !== 'landscape_parameters.json') {
    response = await fetch_manifest('landscape_parameters.json');
  }

  if (response.ok) {
    img.landscape_parameters = await response.json();
    return;
  }

  // No manifest file: `base_url` may point straight at a .zarr store that keeps its
  // profile in the root group's attributes. Tried only after the file, so a DegaFiles
  // bundle never pays for this request.
  const fromRoot = await readRootManifest(fetch_url, base_url);
  if (fromRoot) {
    img.landscape_parameters = fromRoot;
    return;
  }

  throw new Error(
    `Failed to fetch ${manifest_name}: ${response.status} ${response.statusText}. ` +
      `No ${ROOT_MANIFEST_KEY} block in ${base_url}/zarr.json either, so this is ` +
      `neither a DegaFiles bundle nor a spatially tiled SpatialData store.`
  );
};

/**
 * Read the profile out of a Zarr group's attributes.
 *
 * @returns the manifest, or null when this is not such a store
 */
async function readRootManifest(fetch_url, base_url) {
  try {
    const response = await fetch_url(`${base_url}/zarr.json`);
    if (!response.ok) return null;
    const root = await response.json();
    const manifest = root?.attributes?.[ROOT_MANIFEST_KEY];
    return manifest ? celldegaParametersFromSpatialTiling(manifest) : null;
  } catch {
    // A store that is not reachable is reported by the caller's error, not here.
    return null;
  }
}
