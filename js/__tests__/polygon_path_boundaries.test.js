/* global require */

const fs = require('fs');
const path = require('path');

const loadExports = (relativePath, names) => {
  const source = fs
    .readFileSync(path.join(__dirname, relativePath), 'utf8')
    .replace(/^export const /gm, 'const ');
  return new Function(`${source}\nreturn { ${names.join(', ')} };`)();
};

const { concatenate_polygon_data } = loadExports(
  '../vector_tile/concatenate_functions.js',
  ['concatenate_polygon_data']
);
const { extractPolygonPaths } = loadExports(
  '../vector_tile/polygons/extractPolygonPaths.js',
  ['extractPolygonPaths']
);

const polygonData = (length, offsets, coordinates) => ({
  length,
  startIndices: new Int32Array(offsets),
  attributes: {
    getPolygon: { value: new Float64Array(coordinates), size: 2 },
  },
});

describe('polygon path boundaries', () => {
  test('ignores offsets and coordinates beyond the logical row count', () => {
    const first = polygonData(1, [0, 3, 0, 0], [1, 1, 2, 1, 1, 1, 999, 999]);
    const second = polygonData(1, [0, 3], [10, 10, 11, 10, 10, 10]);

    const combined = concatenate_polygon_data([first, second]);

    expect(combined.length).toBe(2);
    expect(Array.from(combined.startIndices)).toEqual([0, 3, 6]);
    expect(extractPolygonPaths(combined)).toEqual([
      [
        [1, 1],
        [2, 1],
        [1, 1],
      ],
      [
        [10, 10],
        [11, 10],
        [10, 10],
      ],
    ]);
    expect(extractPolygonPaths(first)).toHaveLength(1);
  });

  test('normalizes sliced coordinate spans before combining tiles', () => {
    const sliced = polygonData(
      1,
      [2, 5],
      [-10, -10, -9, -9, 1, 1, 2, 1, 1, 1, 99, 99]
    );
    const next = polygonData(1, [0, 3], [10, 10, 11, 10, 10, 10]);
    const combined = concatenate_polygon_data([sliced, next]);

    expect(Array.from(combined.startIndices)).toEqual([0, 3, 6]);
    expect(combined.attributes.getPolygon.value).toHaveLength(12);
    expect(extractPolygonPaths(combined)).toEqual([
      [
        [1, 1],
        [2, 1],
        [1, 1],
      ],
      [
        [10, 10],
        [11, 10],
        [10, 10],
      ],
    ]);
  });

  test('retains legitimate empty rows so cell names remain aligned', () => {
    const data = polygonData(
      3,
      [0, 3, 3, 6],
      [1, 1, 2, 1, 1, 1, 10, 10, 11, 10, 10, 10]
    );
    const expected = [
      [
        [1, 1],
        [2, 1],
        [1, 1],
      ],
      [],
      [
        [10, 10],
        [11, 10],
        [10, 10],
      ],
    ];

    expect(extractPolygonPaths(data)).toEqual(expected);
    expect(extractPolygonPaths(concatenate_polygon_data([data]))).toEqual(
      expected
    );
  });

  test.each([
    [0, 3, 999],
    [0, 3],
    [0, 3, -1],
    [0, 3, 2],
  ])('rejects invalid offsets %j', (...offsets) => {
    const data = polygonData(2, offsets, [1, 1, 2, 1, 1, 1]);
    expect(() => extractPolygonPaths(data)).toThrow('offsets');
    expect(() => concatenate_polygon_data([data])).toThrow('offsets');
  });

  test.each([NaN, Infinity, -Infinity])(
    'rejects nonfinite coordinate %s before publishing any outlines',
    (invalid) => {
      const data = polygonData(
        2,
        [0, 3, 6],
        [1, 1, invalid, 1, 1, 1, 10, 10, 11, 10, 10, 10]
      );
      expect(() => extractPolygonPaths(data)).toThrow('coordinate');
    }
  );

  test('uses a terminal zero offset for empty or missing tile data', () => {
    const empty = concatenate_polygon_data([
      null,
      undefined,
      polygonData(0, [0], []),
    ]);
    expect(empty.length).toBe(0);
    expect(Array.from(empty.startIndices)).toEqual([0]);
    expect(extractPolygonPaths(empty)).toEqual([]);
  });
});
