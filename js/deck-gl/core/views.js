import { OrthographicView, OrbitView } from 'deck.gl';

import { is_orbit_technology } from '../../global_variables/image_info';

export const set_views = (technology = '') => {
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
  return [new OrthographicView({ id: 'ortho' })];
};
