import { OrthographicView } from 'deck.gl';

const GAP = 4;

export const LANDMARK_VIEW_ID_A = 'landmark-view-a';
export const LANDMARK_VIEW_ID_B = 'landmark-view-b';

/**
 * Two side-by-side OrthographicViews, each independently pannable/zoomable
 * (unlike Yearbook's portrait grid, where only one portrait can pan).
 */
export const create_landmark_views = (width, height) => {
  const panel_width = (width - GAP) / 2;

  return [
    new OrthographicView({
      id: LANDMARK_VIEW_ID_A,
      x: 0,
      y: 0,
      width: panel_width,
      height,
      controller: {
        doubleClickZoom: false,
        dragPan: true,
        scrollZoom: true,
        touchZoom: true,
      },
    }),
    new OrthographicView({
      id: LANDMARK_VIEW_ID_B,
      x: panel_width + GAP,
      y: 0,
      width: panel_width,
      height,
      controller: {
        doubleClickZoom: false,
        dragPan: true,
        scrollZoom: true,
        touchZoom: true,
      },
    }),
  ];
};

export const landmark_panel_width = (width) => (width - GAP) / 2;

export const side_for_viewport_id = (viewport_id) => {
  if (viewport_id === LANDMARK_VIEW_ID_A) return 'a';
  if (viewport_id === LANDMARK_VIEW_ID_B) return 'b';
  return null;
};

export const view_id_for_side = (side) =>
  side === 'a' ? LANDMARK_VIEW_ID_A : LANDMARK_VIEW_ID_B;

/**
 * Center + zoom that fits a slice's centroids inside one panel, so swapping
 * to a very differently-scaled slice starts from a sane view.
 */
export const initial_view_state_for_centroids = (
  rows,
  panel_width,
  panel_height
) => {
  if (!rows.length) {
    return { target: [0, 0, 0], zoom: 0 };
  }

  let min_x = Infinity;
  let max_x = -Infinity;
  let min_y = Infinity;
  let max_y = -Infinity;

  rows.forEach((row) => {
    if (row.x < min_x) min_x = row.x;
    if (row.x > max_x) max_x = row.x;
    if (row.y < min_y) min_y = row.y;
    if (row.y > max_y) max_y = row.y;
  });

  const span_x = Math.max(max_x - min_x, 1e-6);
  const span_y = Math.max(max_y - min_y, 1e-6);
  const zoom =
    Math.log2(Math.min(panel_width / span_x, panel_height / span_y)) - 0.2;

  return {
    target: [(min_x + max_x) / 2, (min_y + max_y) / 2, 0],
    zoom,
  };
};
