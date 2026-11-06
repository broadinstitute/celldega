/** @jest-environment node */
/* global require */

const fs = require('node:fs');
const path = require('node:path');

const arrow = require('apache-arrow');
const pq = require('parquet-wasm/node');

const source = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const { arrayBufferToArrowTable, wasmTableToArrowTable } = new Function(
  'arrow',
  'getPq',
  'handleAsyncError',
  `${source('read_parquet/arrayBufferToArrowTable.js')}
   return { arrayBufferToArrowTable, wasmTableToArrowTable };`
)(
  arrow,
  async () => pq,
  (error) => ({ message: error.message })
);

const { set_cell_cats, getCellColorContext, isCellVisible } = new Function(`
  ${source('read_parquet/table_accessors.js')}
  ${source('global_variables/cat.js')}
  ${source('deck-gl/layers/cell_color.js')}
  return { set_cell_cats, getCellColorContext, isCellVisible };
`)();

// Synthetic pandas/pyarrow export: uint32 names 0..2049, categorical strings
// A/B for rows 0..1023, C/B for 1024..2047, then D/D. The category dictionary
// changes after parquet-wasm's first 1024-row batch. No scientific data is used.
const parquetBytes = () =>
  Uint8Array.from(
    Buffer.from(
      fs.readFileSync(
        path.join(__dirname, 'fixtures/dictionary_clusters.parquet.base64'),
        'utf8'
      ),
      'base64'
    )
  );

const expectedCategories = [
  ...Array.from({ length: 1024 }, (_, i) => (i % 2 ? 'B' : 'A')),
  ...Array.from({ length: 1024 }, (_, i) => (i % 2 ? 'B' : 'C')),
  'D',
  'D',
];

test('preserves dictionary labels across real Parquet record batches and cluster filtering', () => {
  const wasmTable = pq.readParquet(parquetBytes());
  expect(wasmTable.numBatches).toBeGreaterThan(1);
  const free = jest.spyOn(wasmTable, 'free');
  const table = wasmTableToArrowTable(wasmTable);
  expect(free).toHaveBeenCalledTimes(1);

  const cats = {
    cat: 'cluster',
    cell_ids_are_indexed: true,
    cell_names_array: expectedCategories.map((_, index) => `cell-${index}`),
    selected_cats: ['C'],
    color_dict_cluster: {
      A: [255, 0, 0],
      B: [0, 255, 0],
      C: [0, 0, 255],
      D: [255, 255, 0],
    },
  };
  set_cell_cats(cats, table, 'cluster');
  expect(cats.cell_cats).toEqual(expectedCategories);

  const context = getCellColorContext(cats);
  const visible = cats.cell_cats.flatMap((_, index) =>
    isCellVisible(context, index) ? [index] : []
  );
  expect(visible).toEqual(
    Array.from({ length: 512 }, (_, index) => 1024 + index * 2)
  );
});

test('uses the corrected decoder through the public ArrayBuffer entry point', async () => {
  const table = await arrayBufferToArrowTable(parquetBytes().buffer);
  expect(table.getChild('cluster').toArray()).toEqual(expectedCategories);
});

test('keeps a whole-table IPC fast path for multiple non-dictionary batches', () => {
  const first = arrow.tableFromArrays({ name: Uint32Array.from([0, 1]) });
  const second = arrow.tableFromArrays({ name: Uint32Array.from([2, 3]) });
  const whole = new arrow.Table([...first.batches, ...second.batches]);
  const firstIPC = arrow.tableToIPC(first, 'stream');
  const wholeIPC = arrow.tableToIPC(whole, 'stream');
  const wasmTable = {
    numBatches: 2,
    recordBatch: jest.fn(() => ({ intoIPCStream: () => firstIPC })),
    intoIPCStream: jest.fn(() => wholeIPC),
    free: jest.fn(),
  };

  expect(wasmTableToArrowTable(wasmTable).getChild('name').toArray()).toEqual(
    Uint32Array.from([0, 1, 2, 3])
  );
  expect(wasmTable.recordBatch).toHaveBeenCalledTimes(1);
  expect(wasmTable.intoIPCStream).toHaveBeenCalledTimes(1);
  expect(wasmTable.free).not.toHaveBeenCalled();
});

test('uses whole-table IPC directly for a single batch', () => {
  const table = arrow.tableFromArrays({ name: Uint32Array.from([0]) });
  const wasmTable = {
    numBatches: 1,
    recordBatch: jest.fn(),
    intoIPCStream: jest.fn(() => arrow.tableToIPC(table, 'stream')),
    free: jest.fn(),
  };
  expect(wasmTableToArrowTable(wasmTable).numRows).toBe(1);
  expect(wasmTable.recordBatch).not.toHaveBeenCalled();
  expect(wasmTable.free).not.toHaveBeenCalled();
});

test('frees the parent table if a batch cannot be converted', () => {
  const wasmTable = {
    numBatches: 2,
    recordBatch: jest.fn(() => ({
      intoIPCStream: () => {
        throw new Error('Cannot serialize batch');
      },
    })),
    free: jest.fn(),
  };
  expect(() => wasmTableToArrowTable(wasmTable)).toThrow(
    'Cannot serialize batch'
  );
  expect(wasmTable.free).toHaveBeenCalledTimes(1);
});
