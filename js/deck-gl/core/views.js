import { OrbitView, OrthographicView } from 'deck.gl';

export const set_views = (is3d = false) => {
  if (is3d) {
    return [new OrbitView({ id: 'ortho' })];
  }
  return [new OrthographicView({ id: 'ortho' })];
};
