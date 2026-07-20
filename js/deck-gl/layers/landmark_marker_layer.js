import { IconLayer } from 'deck.gl';

import { getModelMatrixProps } from '../../utils/rotation';

const ICON_SIZE = 64;

const DRAFT_COLOR = [255, 165, 0];
const COMMITTED_COLOR = [40, 80, 220];
const SELECTED_COLOR = [220, 40, 60];

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

/**
 * Features keep their true (data-space) coordinates in `geometry.coordinates`
 * — `rotation_state` is applied as a GPU `modelMatrix`, mirroring
 * `ini_landmark_cell_layer`. Picked/dragged screen coordinates must be
 * unrotated (see `rotate_point_inverse` in `utils/rotation`) before being
 * written back into a feature's geometry.
 */
export const ini_landmark_marker_layer = (
  side,
  features,
  { selected_label, rotation_state, visible = true } = {}
) =>
  new IconLayer({
    id: `landmark-icon-${side}`,
    data: features,
    visible,
    iconAtlas: PENTAGON_ICON_ATLAS,
    iconMapping: PENTAGON_ICON_MAPPING,
    getIcon: () => 'pentagon',
    getPosition: (f) => f.geometry.coordinates,
    getSize: 18,
    sizeUnits: 'pixels',
    getColor: (f) => {
      if (f.properties.label === selected_label) return SELECTED_COLOR;
      return f.properties.draft ? DRAFT_COLOR : COMMITTED_COLOR;
    },
    pickable: true,
    updateTriggers: {
      getColor: [selected_label],
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
