import * as d3 from 'd3';
import { ScatterplotLayer, TextLayer } from 'deck.gl';

import { hexToRgb } from '../../utils/hexToRgb';
import { getModelMatrixProps } from '../../utils/rotation';

// Data-space (micron) radii — larger than Landscape's 5.0 cell radius so a
// landmark reads as distinct from the cells it sits among. Zoom-scaled, but
// clamped to a clickable floor / sane ceiling in pixels by the layer.
const DEFAULT_RADIUS = 20;
const MODIFY_TARGET_RADIUS = 30; // the landmark being edited draws larger
const LINE_WIDTH = 2;
const DRAFT_LINE_ALPHA = 170;
const DRAFT_FILL_ALPHA = 45;
const FILL_ALPHA = 70; // translucent so cells stay visible through the disc
// Every landmark other than the one actively being placed/dragged/renamed
// dims out, so it's obvious which one you're working on.
const DIMMED_LINE_ALPHA = 90;
const DIMMED_FILL_ALPHA = 22;

// The golden angle spaces consecutive hues maximally far apart around the
// wheel (unlike a plain modulo step, it never falls into a short repeating
// cycle) -- landmarks default to auto-incrementing numeric labels, so this
// gives sequentially-created landmarks (1, 2, 3, ...) reliably distinct
// colors instead of a hash's occasional near-collisions.
const GOLDEN_ANGLE_DEGREES = 137.50776;

const hash_string_to_hue = (value) => {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash % 360;
};

/** A deterministic, distinct default color per landmark label — same label
 * always gets the same color, with no coordination needed between the
 * marker layer and the LNDMRK/SLICE bar graphs (they call this too).
 * Numeric labels (the common case -- landmarks are auto-numbered unless
 * renamed) use golden-angle hue spacing; non-numeric custom names fall back
 * to a hash, since there's no "index" to space them by. */
export const color_for_label = (label) => {
  const numeric = Number(label);
  const hue = Number.isFinite(numeric)
    ? (numeric * GOLDEN_ANGLE_DEGREES) % 360
    : hash_string_to_hue(String(label));
  const { r, g, b } = d3.hsl(hue, 0.65, 0.5).rgb();
  return [Math.round(r), Math.round(g), Math.round(b)];
};

/** `color_overrides` is the `landmark_colors` trait (`{label: "#rrggbb"}`)
 * — a user-picked color always wins over the computed default. */
export const resolve_landmark_color = (label, color_overrides = {}) => {
  const override = color_overrides[String(label)];
  return override ? hexToRgb(override) : color_for_label(label);
};

/**
 * A landmark is drawn as an outlined circle (`ScatterplotLayer`): a solid
 * ring in the landmark's color over a translucent fill, so cells stay
 * visible through it and the whole disc is an easy, reliable click/drag
 * target (a mostly-transparent icon was near-impossible to grab).
 *
 * `getRadius` is in data-space units (deck.gl's default `radiusUnits:
 * 'meters'`, same as Landscape's cell layer), so markers scale with zoom —
 * `radiusMinPixels`/`radiusMaxPixels` keep them clickable when zoomed out
 * and from swamping the view when zoomed in. Features keep their true
 * (data-space) coordinates in `geometry.coordinates`; `rotation_state` is
 * applied as a GPU `modelMatrix`, mirroring `ini_landmark_cell_layer`.
 * Picked/dragged screen coordinates must be unrotated (see
 * `rotate_point_inverse`) before being written back into a feature's geometry.
 *
 * Every label gets its own distinct, stable color (`color_for_label`); an
 * unsaved draft is a translucent preview of that same color; the landmark
 * currently targeted in MODIFY renders larger; and every *other* landmark
 * dims out whenever there's a `focus_label` (the one being placed in MARK,
 * or dragged/renamed/deleted in MODIFY), so it stands out from the rest.
 */
export const ini_landmark_marker_layer = (
  side,
  features,
  {
    rotation_state,
    visible = true,
    modify_target = null,
    focus_label = null,
    color_overrides = {},
  } = {}
) =>
  new ScatterplotLayer({
    id: `landmark-marker-${side}`,
    data: features,
    visible,
    getPosition: (f) => f.geometry.coordinates,
    getRadius: (f) =>
      f.properties.label === modify_target
        ? MODIFY_TARGET_RADIUS
        : DEFAULT_RADIUS,
    radiusMinPixels: 4,
    radiusMaxPixels: 40,
    stroked: true,
    filled: true,
    lineWidthUnits: 'pixels',
    getLineWidth: LINE_WIDTH,
    lineWidthMinPixels: LINE_WIDTH,
    getFillColor: (f) => {
      const [r, g, b] = resolve_landmark_color(
        f.properties.label,
        color_overrides
      );
      if (f.properties.draft) return [r, g, b, DRAFT_FILL_ALPHA];
      const dimmed = focus_label != null && f.properties.label !== focus_label;
      return [r, g, b, dimmed ? DIMMED_FILL_ALPHA : FILL_ALPHA];
    },
    getLineColor: (f) => {
      const [r, g, b] = resolve_landmark_color(
        f.properties.label,
        color_overrides
      );
      if (f.properties.draft) return [r, g, b, DRAFT_LINE_ALPHA];
      const dimmed = focus_label != null && f.properties.label !== focus_label;
      return [r, g, b, dimmed ? DIMMED_LINE_ALPHA : 255];
    },
    pickable: true,
    updateTriggers: {
      getRadius: [modify_target],
      getFillColor: [color_overrides, focus_label],
      getLineColor: [color_overrides, focus_label],
    },
    ...getModelMatrixProps(rotation_state),
  });

/**
 * Small, semi-transparent text labels sitting just above each landmark marker,
 * so a slice full of markers stays readable (which one is `tongue-3`?) without
 * having to hover each. Same `rotation_state` modelMatrix as the marker layer,
 * so labels ride along with a rotated slice. Not pickable — clicks/drags should
 * always hit the marker disc underneath, never the text.
 */
export const ini_landmark_label_layer = (
  side,
  features,
  { rotation_state, visible = true, color_overrides = {} } = {}
) =>
  new TextLayer({
    id: `landmark-label-${side}`,
    data: features,
    visible,
    getPosition: (f) => f.geometry.coordinates,
    getText: (f) => String(f.properties.label),
    getColor: (f) => {
      const [r, g, b] = resolve_landmark_color(
        f.properties.label,
        color_overrides
      );
      return [r, g, b, 180];
    },
    getSize: 12,
    sizeUnits: 'pixels',
    getPixelOffset: [0, -11], // just above the disc
    getTextAnchor: 'middle',
    getAlignmentBaseline: 'bottom',
    fontFamily: 'monospace',
    fontWeight: 'bold',
    characterSet: 'auto',
    pickable: false,
    ...getModelMatrixProps(rotation_state),
  });

/** Committed-only (never drafts) GeoJSON FeatureCollection, matching the
 * `landmark_geojson_a`/`_b` wire shape the Python widget expects. */
export const features_to_geojson = (features) => ({
  type: 'FeatureCollection',
  features: features
    .filter((f) => !f.properties.draft)
    .map((f) => ({
      type: 'Feature',
      geometry: f.geometry,
      properties: { label: f.properties.label },
    })),
});

export const geojson_to_features = (geojson) =>
  (geojson?.features || []).map((f) => ({
    type: 'Feature',
    geometry: f.geometry,
    properties: { label: f.properties.label, draft: false },
  }));
