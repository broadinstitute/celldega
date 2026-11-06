/** @jest-environment node */
/* global require */

const fs = require('fs');
const path = require('path');

const arrow = require('apache-arrow');

const readSource = (relativePath) =>
  fs
    .readFileSync(path.join(__dirname, relativePath), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const { get_polygon_data, concatenate_polygon_data, extractPolygonPaths } =
  new Function(`
    ${readSource('../vector_tile/concatenate_functions.js')}
    ${readSource('../read_parquet/get_polygon_data.js')}
    ${readSource('../vector_tile/polygons/extractPolygonPaths.js')}
    return { get_polygon_data, concatenate_polygon_data, extractPolygonPaths };
  `)();

const pointType = new arrow.List(
  new arrow.Field('item', new arrow.Float64(), false)
);
const ringType = new arrow.List(new arrow.Field('item', pointType, false));
const polygonType = new arrow.List(new arrow.Field('item', ringType, false));
const polygon = (x) => [
  [
    [x, 0],
    [x + 2, 0],
    [x + 2, 2],
    [x, 0],
  ],
];
const makeTable = (positions) =>
  new arrow.Table({
    GEOMETRY: arrow.vectorFromArray(positions.map(polygon), polygonType),
  });
const ipcRoundTrip = (table) => arrow.tableFromIPC(arrow.tableToIPC(table));
const expectedPaths = (positions) => positions.map((x) => polygon(x)[0]);

describe('polygon Arrow decoding', () => {
  test('ignores alignment padding in real Arrow IPC offset buffers', () => {
    const table = ipcRoundTrip(makeTable([0, 10]));
    const chunk = table.getChild('GEOMETRY').data[0];

    // Three logical offsets occupy a four-element aligned IPC buffer.
    expect(chunk.valueOffsets.length).toBeGreaterThan(chunk.length + 1);

    const data = get_polygon_data(table);
    expect(data.length).toBe(2);
    expect(Array.from(data.startIndices)).toEqual([0, 4, 8]);
    expect(extractPolygonPaths(data)).toEqual(expectedPaths([0, 10]));
  });

  test('concatenating padded tiles never creates a path connecting cells', () => {
    const tables = [
      ipcRoundTrip(makeTable([0, 10])),
      ipcRoundTrip(makeTable([100, 110])),
    ];
    const data = concatenate_polygon_data(tables.map(get_polygon_data));

    expect(data.length).toBe(4);
    expect(Array.from(data.startIndices)).toEqual([0, 4, 8, 12, 16]);
    expect(extractPolygonPaths(data)).toEqual(expectedPaths([0, 10, 100, 110]));
  });

  test('decodes multiple row-group chunks with aligned offset buffers', () => {
    const table = ipcRoundTrip(makeTable([0, 10])).concat(
      ipcRoundTrip(makeTable([100, 110]))
    );
    expect(table.getChild('GEOMETRY').data).toHaveLength(2);

    const data = get_polygon_data(table);
    expect(data.length).toBe(table.numRows);
    expect(extractPolygonPaths(data)).toEqual(expectedPaths([0, 10, 100, 110]));
  });

  test('rebases sliced lists and copies only their selected coordinates', () => {
    const original = ipcRoundTrip(makeTable([0, 10, 20]));
    const sliced = original.slice(1, 2);
    const data = get_polygon_data(sliced);

    expect(data.length).toBe(1);
    expect(Array.from(data.startIndices)).toEqual([0, 4]);
    expect(data.attributes.getPolygon.value).toHaveLength(8);
    expect(extractPolygonPaths(data)).toEqual(expectedPaths([10]));

    const combined = concatenate_polygon_data([
      data,
      get_polygon_data(ipcRoundTrip(makeTable([100, 110])).slice(1, 2)),
    ]);
    expect(extractPolygonPaths(combined)).toEqual(expectedPaths([10, 110]));

    const coordinates =
      original.getChild('GEOMETRY').data[0].children[0].children[0].children[0]
        .values;
    coordinates[8] = 999;
    expect(extractPolygonPaths(data)).toEqual(expectedPaths([10]));
  });

  test('skips empty chunks without losing the following chunk geometry', () => {
    const first = makeTable([0]);
    const table = first.concat(first.slice(0, 0), makeTable([100]));
    expect(extractPolygonPaths(get_polygon_data(table))).toEqual(
      expectedPaths([0, 100])
    );
  });

  test('rejects decreasing offsets instead of creating a path across cells', () => {
    const table = ipcRoundTrip(makeTable([0, 10]));
    table.getChild('GEOMETRY').data[0].valueOffsets[2] = 0;

    expect(() => get_polygon_data(table)).toThrow('coordinate offsets');
  });

  test('rejects coordinates outside their logical buffer bounds', () => {
    const table = ipcRoundTrip(makeTable([0]));
    const ringChunk = table.getChild('GEOMETRY').data[0].children[0];
    ringChunk.valueOffsets[1] = 1000;

    expect(() => get_polygon_data(table)).toThrow('coordinate offsets');
  });

  test('rejects non-finite coordinates before publishing polygon paths', () => {
    const table = ipcRoundTrip(makeTable([0]));
    table.getChild(
      'GEOMETRY'
    ).data[0].children[0].children[0].children[0].values[0] = NaN;

    expect(() => get_polygon_data(table)).toThrow('non-finite coordinate');
  });
});
