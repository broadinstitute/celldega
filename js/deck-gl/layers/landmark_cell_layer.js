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

const HIGHLIGHT_RING_COLOR = [0, 0, 0, 255];

/**
 * Cell rows keep their true (data-space) x/y; `rotation_state` (from
 * `build_rotation_state`, same helper Landscape's `rotate` uses) is applied
 * as a GPU `modelMatrix`, not a per-point transform, so a coarse manual
 * rotation can assist visual alignment without touching the coordinates
 * landmarks get stored in. `highlight_cluster` is shared across both sides
 * (one CELL bar, not per-side), so selecting a cluster dims non-matching
 * cells identically on both views. `highlighted_cell` is a per-side pick (a
 * single `cell_id`), drawn with a dark outline ring as a visual anchor while
 * placing a nearby landmark — independent of cluster highlighting. `radius`
 * is the widget's fixed `cell_radius` trait (not runtime-adjustable);
 * `opacity` is what the CELL control's slider actually drives.
 */
export const ini_landmark_cell_layer = (
  side,
  rows,
  {
    highlight_cluster,
    rotation_state,
    visible = true,
    radius = 3,
    opacity = 0.86,
    highlighted_cell = null,
  } = {}
) =>
  new ScatterplotLayer({
    id: `landmark-cell-${side}`,
    data: rows,
    visible,
    getPosition: (d) => [d.x, d.y],
    getFillColor: (d) => {
      const rgb = d.color ? hexToRgb(d.color) : DEFAULT_COLOR;
      const alpha = Math.round(255 * opacity);
      if (highlight_cluster && d.cluster !== highlight_cluster) {
        return [...rgb, Math.round(alpha * 0.05)];
      }
      return [...rgb, alpha];
    },
    getRadius: radius,
    radiusUnits: 'pixels',
    radiusMinPixels: 1.5,
    stroked: true,
    getLineColor: (d) =>
      d.cell_id === highlighted_cell ? HIGHLIGHT_RING_COLOR : [0, 0, 0, 0],
    getLineWidth: 1,
    lineWidthUnits: 'pixels',
    pickable: true,
    updateTriggers: {
      getFillColor: [highlight_cluster, opacity],
      getRadius: [radius],
      getLineColor: [highlighted_cell],
    },
    ...getModelMatrixProps(rotation_state),
  });
