import { ScatterplotLayer } from 'deck.gl';

import { hexToRgb } from '../../utils/hexToRgb';
import { getModelMatrixProps } from '../../utils/rotation';

const DEFAULT_COLOR = [79, 128, 255];

/**
 * Rows decoded from a Landmark centroid parquet payload (see
 * `_slice_centroids` in celldega/align/widget.py): cell_id, x, y, and
 * optionally cluster + color.
 */
export const centroid_rows_from_parquet = (parsed) => {
  const { result, attr } = parsed;
  const x_idx = attr.indexOf('x');
  const y_idx = attr.indexOf('y');
  const color_idx = attr.indexOf('color');
  const cluster_idx = attr.indexOf('cluster');

  return Object.entries(result).map(([cell_id, values]) => ({
    cell_id,
    x: Number(values[x_idx]),
    y: Number(values[y_idx]),
    color: color_idx >= 0 ? values[color_idx] : null,
    cluster: cluster_idx >= 0 ? values[cluster_idx] : null,
  }));
};

/** Distinct (cluster, color) pairs present in a side's centroid rows, for the legend. */
export const cluster_categories = (rows) => {
  const seen = new Map();
  rows.forEach((row) => {
    if (row.cluster != null && !seen.has(row.cluster)) {
      seen.set(row.cluster, row.color || '#4f80ff');
    }
  });
  return Array.from(seen, ([cluster, color]) => ({ cluster, color }));
};

/**
 * Cell rows keep their true (data-space) x/y; `rotation_state` (from
 * `build_rotation_state`, same helper Landscape's `rotate` uses) is applied
 * as a GPU `modelMatrix`, not a per-point transform, so a coarse manual
 * rotation can assist visual alignment without touching the coordinates
 * landmarks get stored in.
 */
export const ini_landmark_cell_layer = (
  side,
  rows,
  { highlight_cluster, rotation_state } = {}
) =>
  new ScatterplotLayer({
    id: `landmark-cell-${side}`,
    data: rows,
    getPosition: (d) => [d.x, d.y],
    getFillColor: (d) => {
      const rgb = d.color ? hexToRgb(d.color) : DEFAULT_COLOR;
      if (highlight_cluster && d.cluster !== highlight_cluster) {
        return [...rgb, 50];
      }
      return [...rgb, 220];
    },
    getRadius: 3,
    radiusUnits: 'pixels',
    radiusMinPixels: 1.5,
    pickable: true,
    updateTriggers: {
      getFillColor: [highlight_cluster],
    },
    ...getModelMatrixProps(rotation_state),
  });
