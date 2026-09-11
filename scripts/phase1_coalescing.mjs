/**
 * How much does column projection actually save, and what does it depend on?
 *
 * The headline "44% saved" is not the sum of the requested columns: parquet-wasm coalesces
 * nearby byte ranges into one request, so any column physically between two requested ones
 * is fetched too. That makes the saving depend on where columns sit in the file, which is a
 * writer-side concern -- so it is measured here rather than assumed.
 */

import fs from 'node:fs';

import * as arrow from 'apache-arrow';
import * as pq from 'parquet-wasm/esm/parquet_wasm.js';

const wasmBytes = fs.readFileSync(
  new URL(
    '../node_modules/parquet-wasm/esm/parquet_wasm_bg.wasm',
    import.meta.url
  )
);
try {
  pq.initSync({ module: wasmBytes });
} catch {
  pq.initSync(wasmBytes);
}

const URL_ = process.env.PARQUET_URL;
const RG = Number(process.env.ROW_GROUP ?? 152);

let bytes = 0;
let requests = 0;
const real = globalThis.fetch;
globalThis.fetch = async (...args) => {
  const response = await real(...args);
  bytes += (
    await response
      .clone()
      .arrayBuffer()
      .catch(() => new ArrayBuffer(0))
  ).byteLength;
  requests += 1;
  return response;
};

const file = await pq.ParquetFile.fromUrl(URL_);
const toArrow = (t) => arrow.tableFromIPC(t.intoIPCStream());

const measure = async (label, columns) => {
  bytes = 0;
  requests = 0;
  const table = toArrow(
    await file.read(
      columns ? { rowGroups: [RG], columns } : { rowGroups: [RG] }
    )
  );
  const got = table.schema.fields.map((f) => f.name);
  console.log(
    `  ${label.padEnd(34)} ${(bytes / 1024).toFixed(1).padStart(6)} KiB  ` +
      `${String(requests).padStart(2)} req  ${got.length} col  ${table.numRows} rows`
  );
  return bytes;
};

// Which requests are cheap depends on the file's column order, so the layout is printed
// rather than assumed: v1 writes x y z feature_name..., the canonical layout writes
// x y feature_name z...
const layout = (await file.read({ rowGroups: [RG] })).intoIPCStream();
console.log(
  `\nrow group ${RG}; column order: ${arrow
    .tableFromIPC(layout)
    .schema.fields.map((f) => f.name)
    .slice(0, 4)
    .join(' ')} ...\n`
);
const full = await measure('all 12 columns', null);
await measure('x, y', ['x', 'y']);
await measure('x, y, z', ['x', 'y', 'z']);
await measure('x, y, feature_name', ['x', 'y', 'feature_name']);
await measure('x, __index_level_0__  (first + last)', [
  'x',
  '__index_level_0__',
]);
await measure('x only', ['x']);

console.log(
  `\nA column physically between two requested ones is fetched as well, so the cheap` +
    ` request is whichever one spans the fewest columns in this file's order.`
);
console.log(`Full read for reference: ${(full / 1024).toFixed(1)} KiB\n`);
