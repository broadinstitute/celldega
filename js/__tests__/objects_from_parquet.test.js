/* global require */
const fs = require('fs');
const path = require('path');

const arrow = require('apache-arrow');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

// The parquet bytes are stood in for by the Arrow table they decode to.
const objects_from_parquet = new Function(
  'arrayBufferToArrowTable',
  `${read('read_parquet/table_accessors.js')}
   ${read('read_parquet/objects_from_parquet.js')}
   return objects_from_parquet;`
)(async (table) => table);

test('missing numbers stay missing instead of reading as 0', async () => {
  const table = arrow.tableFromArrays({
    cell_id: ['a', 'b', 'c'],
    score: arrow.vectorFromArray([1.5, null, 0], new arrow.Float64()),
    count: arrow.vectorFromArray([3, null, 1], new arrow.Int32()),
    leiden: ['0', '1', '1'],
  });
  const { result, attr } = await objects_from_parquet(
    { buffer: table },
    'cell_id'
  );
  expect(attr).toEqual(['score', 'count', 'leiden']);
  expect(result.a).toEqual([1.5, 3, '0']);
  expect(result.b).toEqual([null, null, '1']);
  // A real zero is still zero.
  expect(result.c).toEqual([0, 1, '1']);
});
