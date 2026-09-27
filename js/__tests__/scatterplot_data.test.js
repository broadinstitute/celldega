/* global require */

const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(
    path.join(__dirname, '../scatterplot/scatterplot_data.js'),
    'utf8'
  )
  .replace(/^export function /gm, 'function ');
const { prepareScatterplot, cellsInPolygon } = new Function(
  `${source}; return { prepareScatterplot, cellsInPolygon };`
)();

const rows = [
  { cell_id: 'a', x: 0, y: 0 },
  { cell_id: 'b', x: 9, y: 99 },
  { cell_id: 'c', x: 99, y: 9999 },
];

test('log1p changes spacing while retaining raw values and stable identities', () => {
  const linear = prepareScatterplot(rows);
  const log = prepareScatterplot(rows, { xScale: 'log1p', yScale: 'log1p' });
  expect(log.points.map((p) => p.id)).toEqual(['a', 'b', 'c']);
  expect(log.points[1].position[0]).toBeCloseTo(0);
  expect(linear.points[1].position[0]).toBeLessThan(-0.7);
  expect(log.points[1]).toMatchObject({ rawX: 9, rawY: 99 });
  expect(log.domains.x[1]).toBeGreaterThan(Math.log1p(99));
});

test('missing/nonfinite values are omitted rather than coerced to the origin', () => {
  const plot = prepareScatterplot([
    ...rows,
    { cell_id: 'null', x: null, y: 2 },
    { cell_id: 'nan', x: NaN, y: 2 },
    { cell_id: 'inf', x: 1, y: Infinity },
  ]);
  expect(plot.points).toHaveLength(3);
  expect(plot.omitted).toBe(3);
});

test('negative linear coordinates survive and log1p never silently becomes signed log', () => {
  const data = [{ cell_id: 'negative', x: -0.5, y: 0 }, ...rows];
  expect(prepareScatterplot(data).points).toHaveLength(4);
  expect(prepareScatterplot(data, { xScale: 'log1p' }).omitted).toBe(1);
});

test('constant axes and empty plots produce finite domains and positions', () => {
  const plot = prepareScatterplot([{ cell_id: 'single', x: 7, y: 0 }]);
  expect(plot.points[0].position).toEqual([0, 0, 0]);
  expect(plot.domains.x[0]).toBeLessThan(7);
  expect(plot.domains.y[1]).toBeGreaterThan(0);
  expect(prepareScatterplot([])).toEqual({
    points: [],
    domains: { x: [-1, 1], y: [-1, 1] },
    omitted: 0,
  });
});

test('embeddings preserve relative distance on the two axes', () => {
  const plot = prepareScatterplot(rows, { preserveAspect: true });
  const { x, y } = plot.domains;
  expect(x[1] - x[0]).toBeCloseTo(y[1] - y[0]);
  const dx = plot.points[1].position[0] - plot.points[0].position[0];
  const dy = plot.points[1].position[1] - plot.points[0].position[1];
  expect(dx / dy).toBeCloseTo(9 / 99);
});

test('gates include boundary cells and return IDs regardless of input order', () => {
  const points = [
    { id: 'outside', position: [2, 2] },
    { id: 'edge', position: [1, 0] },
    { id: 'inside', position: [0, 0] },
    { id: 'corner', position: [-1, -1] },
  ];
  const polygon = [
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ];
  expect(cellsInPolygon(points, polygon)).toEqual(['edge', 'inside', 'corner']);
  expect(cellsInPolygon(points, polygon.slice().reverse())).toEqual([
    'edge',
    'inside',
    'corner',
  ]);
  expect(cellsInPolygon(points, [])).toEqual([]);
});
