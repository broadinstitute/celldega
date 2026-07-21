import * as d3 from 'd3';
import { IconLayer } from 'deck.gl';

import { getModelMatrixProps } from '../../utils/rotation';

const ICON_SIZE = 64;
const MODIFY_TARGET_SIZE = 22;
const DEFAULT_SIZE = 18;
const DRAFT_ALPHA = 170;

/**
 * A single-icon pentagon atlas (mask:true so IconLayer tints it via getColor)
 * — landmarks need a shape distinct from the circular cell/vertex markers
 * used everywhere else (cells, NBHD polygon vertices).
 */
const build_pentagon_svg = () => {
  const cx = ICON_SIZE / 2;
  const cy = ICON_SIZE / 2;
  const r = ICON_SIZE / 2 - 4;
  const points = Array.from({ length: 5 }, (_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${ICON_SIZE}" height="${ICON_SIZE}"><polygon points="${points}" fill="white"/></svg>`;
};

export const PENTAGON_ICON_ATLAS = `data:image/svg+xml;base64,${btoa(build_pentagon_svg())}`;
export const PENTAGON_ICON_MAPPING = {
  pentagon: { x: 0, y: 0, width: ICON_SIZE, height: ICON_SIZE, mask: true },
};

const hash_string_to_hue = (value) => {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash % 360;
};

/** A deterministic, distinct color per landmark label — same label always
 * gets the same color, with no coordination needed between the marker
 * layer and the LNDMRK/SLICE bar graphs (they call this too). */
export const color_for_label = (label) => {
  const hue = hash_string_to_hue(String(label));
  const { r, g, b } = d3.hsl(hue, 0.65, 0.5).rgb();
  return [Math.round(r), Math.round(g), Math.round(b)];
};

/**
 * Features keep their true (data-space) coordinates in `geometry.coordinates`
 * — `rotation_state` is applied as a GPU `modelMatrix`, mirroring
 * `ini_landmark_cell_layer`. Picked/dragged screen coordinates must be
 * unrotated (see `rotate_point_inverse` in `utils/rotation`) before being
 * written back into a feature's geometry.
 *
 * Every label gets its own distinct, stable color (`color_for_label`);
 * an unsaved draft is a translucent preview of that same color, and the
 * landmark currently targeted in MODIFY renders larger for emphasis.
 */
export const ini_landmark_marker_layer = (
  side,
  features,
  { rotation_state, visible = true, modify_target = null } = {}
) =>
  new IconLayer({
    id: `landmark-icon-${side}`,
    data: features,
    visible,
    iconAtlas: PENTAGON_ICON_ATLAS,
    iconMapping: PENTAGON_ICON_MAPPING,
    getIcon: () => 'pentagon',
    getPosition: (f) => f.geometry.coordinates,
    getSize: (f) =>
      f.properties.label === modify_target ? MODIFY_TARGET_SIZE : DEFAULT_SIZE,
    sizeUnits: 'pixels',
    getColor: (f) => {
      const [r, g, b] = color_for_label(f.properties.label);
      return [r, g, b, f.properties.draft ? DRAFT_ALPHA : 255];
    },
    pickable: true,
    updateTriggers: {
      getSize: [modify_target],
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
