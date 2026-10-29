import { OrthographicView, OrbitView } from 'deck.gl';

import { is_orbit_technology } from '../../global_variables/image_info';

/**
 * @param {string} [technology]
 * @param {{minZoom: number, maxZoom: number}|null} [zoom_limits] - For 2D
 *   views (see landscape_zoom_limits).
 */
export const set_views = (technology = '', zoom_limits = null) => {
  if (is_orbit_technology(technology)) {
    return [
      new OrbitView({
        id: 'orbit',
        // Override the controller's default ±90° pitch limits for every view
        // state, including programmatic camera updates.
        viewState: {
          id: 'orbit',
          minRotationX: -Infinity,
          maxRotationX: Infinity,
        },
      }),
    ];
  }
  return [
    new OrthographicView({
      id: 'ortho',
      // Like the orbit pitch limits above: merged into every view state, so
      // the controller clamps zooming however the camera got there.
      ...(zoom_limits ? { viewState: { id: 'ortho', ...zoom_limits } } : {}),
    }),
  ];
};
