import * as d3 from 'd3';
import { IconLayer } from 'deck.gl';

import { hexToRgb } from '../../utils/hexToRgb';
import { getModelMatrixProps } from '../../utils/rotation';

const ICON_SIZE = 64;
const MODIFY_TARGET_SIZE = 22;
const DEFAULT_SIZE = 18;
const DRAFT_ALPHA = 170;
// Every landmark other than the one actively being placed/dragged/renamed
// dims out, so it's obvious which one you're working on.
const DIMMED_ALPHA = 128;

/**
 * A single-icon target-reticle atlas (mask:true so IconLayer tints it via
 * getColor): a ring with four short inward-pointing ticks, self-generated
 * as an SVG data URI. Unlike a pin (asymmetric, tip-anchored) this is
 * rotationally symmetric about the marked coordinate — which sits exactly
 * at its open center, never obscured by the icon itself — and doesn't need
 * an anchor offset (IconLayer's default anchor is already the icon center).
 */
const build_target_svg = () => {
  const cx = ICON_SIZE / 2;
  const cy = ICON_SIZE / 2;
  const outer_r = ICON_SIZE * 0.375;
  const tick_inner_r = ICON_SIZE * 0.21;
  const stroke_width = ICON_SIZE * 0.08;
  const ticks = [
    [cx, cy - outer_r, cx, cy - tick_inner_r],
    [cx, cy + outer_r, cx, cy + tick_inner_r],
    [cx - outer_r, cy, cx - tick_inner_r, cy],
    [cx + outer_r, cy, cx + tick_inner_r, cy],
  ]
    .map(
      ([x1, y1, x2, y2]) =>
        `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" stroke="white" stroke-width="${stroke_width.toFixed(2)}" stroke-linecap="round"/>`
    )
    .join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${ICON_SIZE}" height="${ICON_SIZE}"><circle cx="${cx}" cy="${cy}" r="${outer_r.toFixed(2)}" fill="none" stroke="white" stroke-width="${stroke_width.toFixed(2)}"/>${ticks}</svg>`;
};

export const TARGET_ICON_ATLAS = `data:image/svg+xml;base64,${btoa(build_target_svg())}`;
export const TARGET_ICON_MAPPING = {
  target: { x: 0, y: 0, width: ICON_SIZE, height: ICON_SIZE, mask: true },
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
  new IconLayer({
    id: `landmark-icon-${side}`,
    data: features,
    visible,
    iconAtlas: TARGET_ICON_ATLAS,
    iconMapping: TARGET_ICON_MAPPING,
    getIcon: () => 'target',
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
      const dimmed = focus_label != null && f.properties.label !== focus_label;
      return [r, g, b, dimmed ? DIMMED_ALPHA : 255];
    },
    pickable: true,
    updateTriggers: {
      getSize: [modify_target],
      getColor: [color_overrides, focus_label],
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
