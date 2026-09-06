/**
 * get_polygon_data must accept every interleaved vertex layout that actually reaches it,
 * and refuse only the one it would read incorrectly.
 *
 * Parquet has no fixed-size-list type, so a writer's `fixed_size_list<n,2>` is stored as
 * a plain List; only readers that honour the embedded ARROW:schema hint (pyarrow)
 * reconstruct the fixed-size type, and parquet-wasm does not. Both forms therefore occur
 * in practice. A guard that demanded FixedSizeList returned null for both DegaFiles and
 * SpatialData, which surfaced as "Cannot destructure property 'startIndices' of null".
 */

/* global require */

const LIST = 12;
const STRUCT = 13;
const FIXED_SIZE_LIST = 16;

let get_polygon_data;

beforeAll(() => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(
      path.join(__dirname, '../read_parquet/get_polygon_data.js'),
      'utf8'
    )
    .replace(/^import[\s\S]*?;$/gm, '')
    .replace(/^export /gm, '');
  // Fixtures below are single-chunk, so the concatenation path is not exercised.
  const code = `const concatenate_polygon_data = () => null;\n${source}\nmodule.exports = { get_polygon_data };`;
  const mod = { exports: {} };
  new Function('module', 'exports', code)(mod, mod.exports);
  ({ get_polygon_data } = mod.exports);
});

// Two triangles: polygon -> ring -> interleaved vertex pairs.
const COORDS = Float64Array.from([0, 0, 4, 0, 0, 4, 10, 10, 14, 10, 10, 14]);
const RING_OFFSETS = Int32Array.from([0, 3, 6]); // vertex units
const POLYGON_OFFSETS = Int32Array.from([0, 1, 2]);

/** Minimal stand-in for an arrow Vector: only what get_polygon_data touches. */
const vec = (typeId, chunk, child) => ({
  data: [{ type: { typeId }, ...chunk }],
  getChildAt: () => child,
});

const buildTable = (vertexTypeId, columnName = 'geometry') => {
  const values = vec(
    3 /* Float */,
    { values: COORDS, length: COORDS.length },
    null
  );
  // A FixedSizeList carries no valueOffsets; a List does. Neither is read at this level.
  const vertex = vec(vertexTypeId, { length: COORDS.length / 2 }, values);
  const ring = vec(LIST, { valueOffsets: RING_OFFSETS, length: 2 }, vertex);
  const polygon = vec(LIST, { valueOffsets: POLYGON_OFFSETS, length: 2 }, ring);
  return {
    getChild: (n) => (n === columnName ? polygon : null),
    getChildAt: () => polygon,
  };
};

describe('vertex layouts', () => {
  test.each([
    ['List (what parquet-wasm produces)', LIST],
    ['FixedSizeList (what pyarrow reconstructs)', FIXED_SIZE_LIST],
  ])('accepts %s', (_label, typeId) => {
    const out = get_polygon_data(buildTable(typeId));
    expect(out).not.toBeNull();
    expect(out.length).toBe(2);
    expect(out.attributes.getPolygon.size).toBe(2);
    expect(Array.from(out.attributes.getPolygon.value)).toEqual(
      Array.from(COORDS)
    );
    // polygon offset -> ring offset -> coordinate index
    expect(Array.from(out.startIndices)).toEqual([0, 3, 6]);
  });

  test('both layouts produce identical output', () => {
    const a = get_polygon_data(buildTable(LIST));
    const b = get_polygon_data(buildTable(FIXED_SIZE_LIST));
    expect(Array.from(a.startIndices)).toEqual(Array.from(b.startIndices));
    expect(Array.from(a.attributes.getPolygon.value)).toEqual(
      Array.from(b.attributes.getPolygon.value)
    );
  });

  test('rejects struct<x, y> rather than reading x as if interleaved', () => {
    // geopandas' geoarrow output. Walking child 0 blindly yields the x column alone and
    // renders wrong polygons with no error, so failing is the correct behaviour.
    expect(get_polygon_data(buildTable(STRUCT))).toBeNull();
  });

  test('returns null when the named column is absent', () => {
    expect(get_polygon_data(buildTable(LIST), 'not_a_column')).toBeNull();
  });

  test('reads the column named by the profile', () => {
    const t = buildTable(LIST, 'display_geometry');
    expect(get_polygon_data(t, 'display_geometry')).not.toBeNull();
  });
});
