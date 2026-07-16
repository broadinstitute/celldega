import { OrthographicView, OrbitView } from 'deck.gl';

import { is_point_cloud_technology } from '../../global_variables/image_info';

export const set_views = (technology = '') => {
  if (is_point_cloud_technology(technology)) {
    return [new OrbitView({ id: 'orbit' })];
  }
  return [new OrthographicView({ id: 'ortho' })];
};
