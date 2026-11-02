/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const { scale_umap_positions } = new Function(
  'is_orbit_technology',
  `${read('umap/scale_umap_data.js')}\nreturn { scale_umap_positions };`
)(() => false);
const gates = new Function(`${read('umap/embedding_gates.js')}
  return { fingerprint, migrate_umap_gates, gate_cell_ids };`)();

const state = (technology = 'Chromium') => ({
  img: { landscape_parameters: { technology } },
  spatial: { x_min: -20, x_max: 33.7, y_min: 8.1, y_max: 26.9 },
});
const bounds = (positions, axis) => {
  const values = Array.from(positions).filter((_, i) => i % 2 === axis);
  return [Math.min(...values), Math.max(...values)];
};

test.each(['Chromium', 'Xenium'])(
  'UMAP Y increases upward with identical XY bounds (%s)',
  (technology) => {
    const raw = new Float64Array([-3.7, -8.4, 0.31, 1.23, 7.1, 2.9]);
    const legacy = scale_umap_positions(
      state(technology),
      raw.slice(),
      2,
      false
    );
    const displayed = scale_umap_positions(state(technology), raw.slice());
    expect(displayed[1]).toBeGreaterThan(displayed[3]);
    expect(displayed[3]).toBeGreaterThan(displayed[5]);
    expect(bounds(displayed, 0)).toEqual(bounds(legacy, 0));
    expect(bounds(displayed, 1)).toEqual(bounds(legacy, 1));
  }
);

test('constant axes, empty buffers and the point-cloud opt-out remain stable', () => {
  const viz = state();
  expect(
    Array.from(scale_umap_positions(viz, new Float64Array([3, 7, 3, 7])))
  ).toEqual([5000, 5000, 5000, 5000]);
  expect(scale_umap_positions(viz, new Float64Array())).toHaveLength(0);
  const cloud = new Float32Array([0, 1, 7, 2, 3, 9]);
  expect(Array.from(scale_umap_positions(viz, cloud, 3, false))).toEqual([
    0, 0, 7, 10000, 10000, 9,
  ]);
});

test.each(['Polygon', 'MultiPolygon'])(
  'migrates legacy %s rings and holes without changing membership',
  (type) => {
    const legacy_positions = new Float64Array([20, 20, 40, 40, 90, 90]);
    const positions = new Float64Array([20, 80, 40, 60, 90, 10]);
    const rings = [
      [
        [10, 10],
        [60, 10],
        [60, 60],
        [10, 60],
        [10, 10],
      ],
      [
        [30, 30],
        [50, 30],
        [50, 50],
        [30, 50],
        [30, 30],
      ],
    ];
    const feature = {
      type: 'Feature',
      geometry: { type, coordinates: type === 'Polygon' ? rings : [rings] },
      properties: {
        coordinate_space: {
          kind: 'umap',
          dataset: 'abc',
          embedding: gates.fingerprint(legacy_positions),
        },
        cell_ids: ['a'],
        cell_count: 1,
      },
    };
    const original = JSON.parse(JSON.stringify(feature));
    const unrelated = {
      ...feature,
      properties: { coordinate_space: { kind: 'xy' } },
    };
    const space = {
      kind: 'umap',
      dataset: 'abc',
      embedding: gates.fingerprint(positions),
      axes: { y: { reversed: true } },
    };
    const collection = {
      type: 'FeatureCollection',
      features: [feature, unrelated],
    };
    const migrated = gates.migrate_umap_gates(
      collection,
      space,
      gates.fingerprint(legacy_positions),
      100
    );
    expect(feature).toEqual(original);
    expect(migrated.features[1]).toBe(unrelated);
    expect(migrated.features[0].properties.cell_ids).toEqual(['a']);
    expect(
      gates.gate_cell_ids(migrated.features[0].geometry, positions, [
        'a',
        'b',
        'c',
      ])
    ).toEqual(['a']);
    expect(
      gates.migrate_umap_gates(
        migrated,
        space,
        gates.fingerprint(legacy_positions),
        100
      )
    ).toBe(migrated);
  }
);
