import { OrthographicView, OrbitView } from 'deck.gl';

const set_yearbook_views = (rows, cols) => {
  const views = [];

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const idx = row * cols + col;
      views.push(
        new OrthographicView({
          id: `yearbook-${idx}`,
          x: `${(col * 100) / cols}%`,
          y: `${(row * 100) / rows}%`,
          width: `${100 / cols}%`,
          height: `${100 / rows}%`,
        })
      );
    }
  }

  return views;
};

export const set_views = (technology = '', yearbook_config = null) => {
  if (technology === 'point-cloud') {
    return [new OrbitView({ id: 'orbit' })];
  }

  if (yearbook_config?.active) {
    const rows = yearbook_config.rows ?? 3;
    const cols = yearbook_config.cols ?? 3;
    return set_yearbook_views(rows, cols);
  }

  return [new OrthographicView({ id: 'ortho' })];
};
