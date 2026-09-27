/** Map one active pair of axes into a stable Cartesian frame for GPU transitions. */
export function prepareScatterplot(
  rows,
  { xScale = 'linear', yScale = 'linear', preserveAspect = false } = {}
) {
  const transform = (value, scale) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return NaN;
    if (scale === 'linear') return value;
    if (scale !== 'log1p') throw new Error(`Unknown scale: ${scale}`);
    return value >= 0 ? Math.log1p(value) : NaN;
  };
  let xmin = Infinity;
  let xmax = -Infinity;
  let ymin = Infinity;
  let ymax = -Infinity;
  const valid = [];
  for (const row of rows) {
    const x = transform(row.x, xScale);
    const y = transform(row.y, yScale);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    xmin = Math.min(xmin, x);
    xmax = Math.max(xmax, x);
    ymin = Math.min(ymin, y);
    ymax = Math.max(ymax, y);
    valid.push({ row, x, y });
  }
  if (!valid.length) {
    return {
      points: [],
      domains: { x: [-1, 1], y: [-1, 1] },
      omitted: rows.length,
    };
  }

  const cx = xmin / 2 + xmax / 2;
  const cy = ymin / 2 + ymax / 2;
  let dx = xmax / 2 - xmin / 2;
  let dy = ymax / 2 - ymin / 2;
  if (preserveAspect) {
    dx = dy =
      Math.max(dx, dy) || Math.max(Math.abs(cx), Math.abs(cy), 1) * 0.05;
  } else {
    dx ||= Math.max(Math.abs(cx), 1) * 0.05;
    dy ||= Math.max(Math.abs(cy), 1) * 0.05;
  }
  // Leave a little space around the extrema, including a constant-valued axis.
  dx *= 1.06;
  dy *= 1.06;
  return {
    points: valid.map(({ row, x, y }) => ({
      id: String(row.cell_id),
      position: [(x - cx) / dx, (y - cy) / dy, 0],
      rawX: row.x,
      rawY: row.y,
      color: row.color || '#4682b4',
      label: row.label == null ? '' : String(row.label),
    })),
    domains: { x: [cx - dx, cx + dx], y: [cy - dy, cy + dy] },
    omitted: rows.length - valid.length,
  };
}

/** Inclusive polygon test in plot coordinates, independent of zoom or cell order. */
export function cellsInPolygon(points, polygon) {
  if (polygon.length < 3) return [];
  return points
    .filter(({ position: [x, y] }) => {
      let inside = false;
      for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const [xi, yi] = polygon[i];
        const [xj, yj] = polygon[j];
        const cross = (x - xi) * (yj - yi) - (y - yi) * (xj - xi);
        const tolerance =
          1e-10 * Math.max(1, Math.abs(xj - xi), Math.abs(yj - yi));
        if (
          Math.abs(cross) <= tolerance &&
          x >= Math.min(xi, xj) - tolerance &&
          x <= Math.max(xi, xj) + tolerance &&
          y >= Math.min(yi, yj) - tolerance &&
          y <= Math.max(yi, yj) + tolerance
        )
          return true;
        if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
          inside = !inside;
        }
      }
      return inside;
    })
    .map((point) => point.id);
}
