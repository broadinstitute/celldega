/* global require */

describe('parquet table accessors', () => {
  let getAlignedColumnArray;
  let getRowKeyArray;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../read_parquet/table_accessors.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { getAlignedColumnArray, getRowKeyArray };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ getAlignedColumnArray, getRowKeyArray } = module.exports);
  });

  const makeTable = (columns, metadata = new Map()) => {
    const fieldNames = Object.keys(columns);
    const firstColumn = columns[fieldNames[0]] || [];

    return {
      numRows: firstColumn.length,
      schema: {
        fields: fieldNames.map((name) => ({ name })),
        metadata,
      },
      getChild: (name) => {
        if (!Object.prototype.hasOwnProperty.call(columns, name)) {
          return null;
        }

        return {
          toArray: () => columns[name],
        };
      },
    };
  };

  test('uses explicit parquet index columns when present', () => {
    const table = makeTable({
      __index_level_0__: ['cell-b', 'cell-a'],
      cluster: ['B', 'A'],
    });

    expect(getRowKeyArray(table)).toEqual(['cell-b', 'cell-a']);
  });

  test('falls back to range row keys for hidden pandas index metadata', () => {
    const table = makeTable({
      color: ['#1f77b4'],
      count: [5717698],
    });

    expect(getRowKeyArray(table, ['cluster', '__index_level_0__'])).toEqual([
      '0',
    ]);
  });

  test('aligns cluster columns to cell metadata names when ids are explicit', () => {
    const table = makeTable({
      __index_level_0__: ['cell-b', 'cell-a'],
      cluster: ['B', 'A'],
    });

    expect(
      getAlignedColumnArray(table, 'cluster', ['cell-a', 'cell-b'])
    ).toEqual(['A', 'B']);
  });

  test('keeps row order when hidden index values are not available', () => {
    const table = makeTable({
      cluster: [0, 0, 1],
    });

    expect(getAlignedColumnArray(table, 'cluster', ['a', 'b', 'c'])).toEqual([
      0, 0, 1,
    ]);
  });
});
