import * as d3 from 'd3';
import { IconLayer } from 'deck.gl';

import { hexToRgb } from '../../utils/hexToRgb';
import { getModelMatrixProps } from '../../utils/rotation';

const ICON_SIZE = 64;
const MODIFY_TARGET_SIZE = 22;
const DEFAULT_SIZE = 18;
const DRAFT_ALPHA = 170;
// In MODIFY, every landmark other than the one being targeted dims out, so
// the one you're actually dragging/renaming/deleting stands out.
const DIMMED_ALPHA = 90;

/**
 * A single-icon map-pin atlas (mask:true so IconLayer tints it via
 * getColor) — same silhouette as deck.gl's own IconLayer example marker,
 * self-generated (rather than fetched from an external atlas image) so a
 * pin still gets a distinct per-landmark tint. The pin's tip -- not its
 * center -- is the anchor (see `PIN_ICON_MAPPING`'s anchorY), so it points
 * exactly at the marked coordinate the way a map pin should.
 */
const build_pin_svg = () => {
  const path =
    'M12 2C8.13 2 5 5.13 5 9c0 4.5 5.5 10.5 6.3 11.34a1 1 0 0 0 1.4 0C13.5 19.5 19 13.5 19 9c0-3.87-3.13-7-7-7z';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${ICON_SIZE}" height="${ICON_SIZE}"><path d="${path}" fill="white"/></svg>`;
};

export const PIN_ICON_ATLAS = `data:image/svg+xml;base64,${btoa(build_pin_svg())}`;
export const PIN_ICON_MAPPING = {
  pin: {
    x: 0,
    y: 0,
    width: ICON_SIZE,
    height: ICON_SIZE,
    anchorX: ICON_SIZE / 2,
    anchorY: ICON_SIZE,
    mask: true,
  },
};

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
 * Features keep their true (data-space) coordinates in `geometry.coordinates`
 * — `rotation_state` is applied as a GPU `modelMatrix`, mirroring
 * `ini_landmark_cell_layer`. Picked/dragged screen coordinates must be
 * unrotated (see `rotate_point_inverse` in `utils/rotation`) before being
 * written back into a feature's geometry.
 *
 * Every label gets its own distinct, stable color (`color_for_label`);
 * an unsaved draft is a translucent preview of that same color; the
 * landmark currently targeted in MODIFY renders larger, and every *other*
 * landmark dims out so the targeted one stands out.
 */
export const ini_landmark_marker_layer = (
  side,
  features,
  {
    rotation_state,
    visible = true,
    modify_target = null,
    color_overrides = {},
  } = {}
) =>
  new IconLayer({
    id: `landmark-icon-${side}`,
    data: features,
    visible,
    iconAtlas: PIN_ICON_ATLAS,
    iconMapping: PIN_ICON_MAPPING,
    getIcon: () => 'pin',
    getPosition: (f) => f.geometry.coordinates,
    getSize: (f) =>
      f.properties.label === modify_target ? MODIFY_TARGET_SIZE : DEFAULT_SIZE,
    sizeUnits: 'pixels',
    getColor: (f) => {
      const [r, g, b] = resolve_landmark_color(
        f.properties.label,
        color_overrides
      );
      if (f.properties.draft) return [r, g, b, DRAFT_ALPHA];
      const dimmed =
        modify_target != null && f.properties.label !== modify_target;
      return [r, g, b, dimmed ? DIMMED_ALPHA : 255];
    },
    pickable: true,
    updateTriggers: {
      getSize: [modify_target],
      getColor: [color_overrides, modify_target],
    },
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
