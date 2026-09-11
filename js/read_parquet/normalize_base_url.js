/**
 * Strip trailing slashes from a base URL.
 *
 * The readers build paths as `${baseUrl}/${directory}/${file}`. If baseUrl already ends
 * in a slash the join produces `//`, which is an empty path segment. That is harmless for
 * a plain relative directory, but it silently breaks one that climbs with `..`:
 *
 *   base 'http://h/s.zarr/visualization/prof/' + '../../points/x.parquet'
 *     -> /s.zarr/visualization/points/x.parquet   (the empty segment absorbs one '..')
 *
 *   base 'http://h/s.zarr/visualization/prof'  + '../../points/x.parquet'
 *     -> /s.zarr/points/x.parquet                 (correct)
 *
 * A SpatialData store points back into itself that way, so normalizing here means callers
 * can pass either form.
 *
 * @param {string} baseUrl - Base URL, with or without trailing slashes
 * @returns {string} - The base URL without trailing slashes
 */
export function normalizeBaseUrl(baseUrl) {
  return typeof baseUrl === 'string' ? baseUrl.replace(/\/+$/, '') : baseUrl;
}

export default normalizeBaseUrl;
