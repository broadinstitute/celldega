import { OrthographicView, OrbitView } from 'deck.gl';

export const set_views = (technology = '') => {
  if (technology === 'point-cloud') {
    return [new OrbitView({ id: 'orbit' })];
  }
  return [new OrthographicView({ id: 'ortho' })];
};
