/* global require */

describe('yearbook portrait centers', () => {
  let compute_portrait_centers;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../viz/yearbook_portrait_centers.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { compute_portrait_centers };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ compute_portrait_centers } = module.exports);
  });

  const FALLBACK = { x: 500, y: 500 };

  // Flat scatter buffer as produced by get_scatter_data: stride = size.
  const scatterData = (values, size) => ({
    length: values.length / size,
    attributes: { getPosition: { value: new Float64Array(values), size } },
  });

  const indexMap = (names) => new Map(names.map((n, i) => [n, i]));

  it('reads distinct centroids per cell from the flat typed-array buffer', () => {
    // stride 2: cell_a -> (10,20), cell_b -> (30,40), cell_c -> (50,60)
    const data = scatterData([10, 20, 30, 40, 50, 60], 2);
    const map = indexMap(['cell_a', 'cell_b', 'cell_c']);

    const centers = compute_portrait_centers(
      ['cell_c', 'cell_a', 'cell_b'],
      map,
      data,
      FALLBACK
    );

    expect(centers).toEqual([
      { cell_id: 'cell_c', x: 50, y: 60 },
      { cell_id: 'cell_a', x: 10, y: 20 },
      { cell_id: 'cell_b', x: 30, y: 40 },
    ]);
  });

  it('does not collapse every portrait onto the fallback (regression)', () => {
    const data = scatterData([1, 2, 3, 4, 5, 6], 2);
    const map = indexMap(['a', 'b', 'c']);

    const centers = compute_portrait_centers(
      ['a', 'b', 'c'],
      map,
      data,
      FALLBACK
    );
    const uniqueXY = new Set(centers.map((c) => `${c.x},${c.y}`));

    // The bug produced 1 unique coordinate (the fallback) for all portraits.
    expect(uniqueXY.size).toBe(3);
    expect(centers.some((c) => c.x === FALLBACK.x && c.y === FALLBACK.y)).toBe(
      false
    );
  });

  it('reads x/y from a 3-coord (x,y,z) buffer using the stride', () => {
    // stride 3: cell_a -> (10,20[,0]), cell_b -> (30,40[,1])
    const data = scatterData([10, 20, 0, 30, 40, 1], 3);
    const map = indexMap(['cell_a', 'cell_b']);

    const centers = compute_portrait_centers(
      ['cell_a', 'cell_b'],
      map,
      data,
      FALLBACK
    );

    expect(centers).toEqual([
      { cell_id: 'cell_a', x: 10, y: 20 },
      { cell_id: 'cell_b', x: 30, y: 40 },
    ]);
  });

  it('falls back for unknown cells and out-of-range indices', () => {
    const data = scatterData([10, 20], 2); // only one cell
    const map = indexMap(['known']);
    map.set('stale', 5); // index past the end of the buffer

    const centers = compute_portrait_centers(
      ['known', 'missing', 'stale'],
      map,
      data,
      FALLBACK
    );

    expect(centers[0]).toEqual({ cell_id: 'known', x: 10, y: 20 });
    expect(centers[1]).toEqual({ cell_id: 'missing', ...FALLBACK });
    expect(centers[2]).toEqual({ cell_id: 'stale', ...FALLBACK });
  });

  it('falls back gracefully when scatter data is missing', () => {
    const centers = compute_portrait_centers(
      ['a'],
      indexMap(['a']),
      undefined,
      FALLBACK
    );
    expect(centers).toEqual([{ cell_id: 'a', ...FALLBACK }]);
  });
});
