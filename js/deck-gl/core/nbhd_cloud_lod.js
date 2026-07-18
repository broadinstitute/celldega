// Zoom-driven semantic zoom for the `neighborhood-cloud` technology: a
// continuous opacity crossfade between the alpha-shape ("shapes") tier and
// the cell tier, with hysteresis so hovering at the boundary zoom level
// doesn't flicker. Returns a small, tier-generic opacity object rather than
// hardcoding exactly two tiers, so a future third tier (e.g. hextiles) can
// slot in without a rewrite of this module.

const clamp01 = (t) => Math.min(1, Math.max(0, t));

// `lodState` is a small mutable bag (`{ band }`) owned by the caller
// (`viz_state.nbhd_cloud.lod_state`) — persisting `band` across calls is what
// makes the fade-in/fade-out threshold pair asymmetric (hysteresis): once
// fully zoomed into 'cells', zooming back out uses the (lower) fade-out
// thresholds, so the crossfade doesn't re-trigger right at the same zoom
// level it just crossed.
export const compute_nbhd_cloud_lod = (zoom, lodState, thresholds) => {
  const {
    fade_in_start: fadeInStart,
    fade_in_end: fadeInEnd,
    fade_out_start: fadeOutStart,
    fade_out_end: fadeOutEnd,
  } = thresholds;

  const [start, end] =
    lodState.band === 'cells'
      ? [fadeOutStart, fadeOutEnd]
      : [fadeInStart, fadeInEnd];

  const t = clamp01((zoom - start) / (end - start));
  lodState.band = t <= 0 ? 'shapes' : t >= 1 ? 'cells' : 'crossfade';

  return { t, fillOpacity: 1 - t, cellOpacity: t };
};

// Nearest-N slice-centroid lookup by plain 3D Euclidean distance (per the
// spec: no spatial index needed, slice counts are small — dozens, not
// thousands). `metaSlice` is the array parsed from `meta_slice.parquet`
// (`{slice_id, centroid_x, centroid_y, centroid_z, ...}`); `n` is the
// nearest-slice count for a given tier (e.g.
// `viz_state.nbhd_cloud.nearest_n_slices.cells`).
export const compute_nearest_slices = (target, metaSlice, n) => {
  const [tx, ty, tz = 0] = target;

  return metaSlice
    .map((s) => ({
      slice_id: s.slice_id,
      dist2:
        (s.centroid_x - tx) ** 2 +
        (s.centroid_y - ty) ** 2 +
        (s.centroid_z - tz) ** 2,
    }))
    .sort((a, b) => a.dist2 - b.dist2)
    .slice(0, n)
    .map((s) => s.slice_id);
};

// Cheap order-independent key for a set of slice ids, used to detect whether
// the nearest-slice set actually changed between debounced viewport updates
// (avoids refetching when panning/zooming without crossing a slice
// boundary).
export const makeSliceSetKey = (sliceIds) =>
  [...sliceIds].map(String).sort().join(',');
