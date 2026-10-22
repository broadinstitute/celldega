/**
 * Zoom limits for a 2D Landscape, so zooming can't run off to a speck or into
 * a single pixel: out to MIN_ZOOM_MARGIN zoom levels past the tissue-wide
 * view, in until the canvas's shorter side spans MAX_ZOOM_VIEW_MICRONS.
 * Panning is not limited.
 */

/** Zoom levels past the tissue-wide view that zooming out may reach. */
export const MIN_ZOOM_MARGIN = 1;

/** Microns across the canvas's shorter side at the maximum zoom. */
export const MAX_ZOOM_VIEW_MICRONS = 10;

const is_finite_number = (value) =>
  typeof value === 'number' && Number.isFinite(value);

/**
 * Zoom at which the tissue (its extent, in data units) fits the canvas; not
 * finite while either size is unknown or zero.
 */
export const zoom_to_fit = (
  canvas_width,
  canvas_height,
  data_width,
  data_height
) =>
  Math.log2(Math.min(canvas_width / data_width, canvas_height / data_height));

/**
 * @param {object} params
 * @param {number} params.fit_zoom - Tissue-wide zoom (see zoom_to_fit).
 * @param {number} [params.initial_zoom] - The view's current (or starting)
 *   zoom; always allowed.
 * @param {number} params.canvas_size - Shorter canvas side, in pixels.
 * @param {number|null} [params.microns_per_unit] - Microns per data unit
 *   (image pixel); data units are taken as microns when unknown.
 * @param {number|null} [params.min_zoom] - The Landscape's `min_zoom`.
 * @param {number|null} [params.max_zoom] - The Landscape's `max_zoom`.
 * @returns {{minZoom: number, maxZoom: number}}
 */
export const landscape_zoom_limits = ({
  fit_zoom,
  initial_zoom,
  canvas_size,
  microns_per_unit,
  min_zoom = null,
  max_zoom = null,
}) => {
  let min = is_finite_number(min_zoom) ? min_zoom : fit_zoom - MIN_ZOOM_MARGIN;
  let max = is_finite_number(max_zoom)
    ? max_zoom
    : Math.log2(
        (canvas_size * (microns_per_unit || 1)) / MAX_ZOOM_VIEW_MICRONS
      );

  if (!is_finite_number(min)) min = -Infinity;
  if (!is_finite_number(max)) max = Infinity;
  if (is_finite_number(initial_zoom)) {
    min = Math.min(min, initial_zoom);
    max = Math.max(max, initial_zoom);
  }

  return { minZoom: min, maxZoom: Math.max(min, max) };
};
