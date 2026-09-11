/**
 * Phase 1: does parquet-wasm column projection work in Celldega's dependency environment?
 *
 * Upstream, `columns` returned correctly projected record batches paired with the
 * *unprojected* schema, so the Arrow IPC buffer was malformed and Arrow JS threw while
 * decoding (kylebarron/parquet-wasm#810). This exercises the experimental fork
 * (@cornhundred/parquet-wasm, PR #811) against a real SpatialData Parquet file.
 *
 * Two things are being separated here, because they can fail independently:
 *   1. is the upstream bug fixed at all
 *   2. does it work against *Celldega's* apache-arrow, which may differ from the version
 *      parquet-wasm was tested with
 *
 * Only the async reader is claimed fixed. `readParquet(bytes, { columns })` silently
 * ignores `columns`, which this also checks so the caveat is verified rather than assumed.
 *
 *   node scripts/phase1_column_projection.mjs        (bundle first; see the header of the run)
 */

import fs from 'node:fs';

import * as arrow from 'apache-arrow';
// The same entry point Celldega's pqInitializer uses, so the build under test is the one
// the viewer would load rather than the `node` target esbuild picks by default.
import * as pq from 'parquet-wasm/esm/parquet_wasm.js';

// wasm-bindgen's web target initialises by fetching; in Node the bytes are read directly.
// Newer builds want a single object, older ones the raw buffer, so both are attempted.
const wasmBytes = fs.readFileSync(
  new URL('../node_modules/parquet-wasm/esm/parquet_wasm_bg.wasm', import.meta.url)
);
try {
  pq.initSync({ module: wasmBytes });
} catch {
  pq.initSync(wasmBytes);
}

const URL_ = process.env.PARQUET_URL;
const RG = Number(process.env.ROW_GROUP ?? 152);
const EXPECTED_ROWS = Number(process.env.EXPECTED_ROWS ?? 1706);

// Ground truth from pyarrow for the same row group, so "it decoded" is distinguished from
// "it decoded the right values".
const EXPECTED_FIRST = {
  x: [107.91187286376953, 112.67183685302734, 122.76412200927734],
  y: [2241.889404296875, 2243.09326171875, 2236.204345703125],
  feature_name: ['PDGFRB', 'PDGFRB', 'FBLN1'],
};

let bytes = 0;
let requests = 0;
const realFetch = globalThis.fetch;
globalThis.fetch = async (...args) => {
  const response = await realFetch(...args);
  const buf = await response.clone().arrayBuffer().catch(() => new ArrayBuffer(0));
  bytes += buf.byteLength;
  requests += 1;
  return response;
};
const meter = () => {
  const snapshot = { bytes, requests };
  bytes = 0;
  requests = 0;
  return snapshot;
};

const results = [];
const check = (name, ok, detail) => {
  results.push({ name, ok });
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` -- ${detail}` : ''}`);
};

const toArrow = (wasmTable) => arrow.tableFromIPC(wasmTable.intoIPCStream());

const names = (table) => table.schema.fields.map((f) => f.name);

const pkg = (rel) =>
  JSON.parse(fs.readFileSync(new URL(rel, import.meta.url), 'utf8'));
console.log(`apache-arrow      : ${pkg('../node_modules/apache-arrow/package.json').version}`);
const pw = pkg('../node_modules/parquet-wasm/package.json');
console.log(`parquet-wasm      : ${pw.name}@${pw.version}`);
console.log(`ParquetFile       : ${typeof pq.ParquetFile === 'function' ? 'present' : 'MISSING'}`);
console.log(`file: ${URL_}\n`);

const file = await pq.ParquetFile.fromUrl(URL_);
const meta = file.metadata();
console.log(`row groups: ${meta.numRowGroups()}\n`);

// --- 1. rowGroups alone (worked before the fix; isolates a regression) --------
meter();
const rgOnly = toArrow(await file.read({ rowGroups: [RG] }));
const rgStats = meter();
check(
  'rowGroups alone decodes',
  rgOnly.numRows === EXPECTED_ROWS,
  `${rgOnly.numRows} rows, ${names(rgOnly).length} columns, ${(rgStats.bytes / 1024).toFixed(1)} KiB`
);

// --- 2. columns alone --------------------------------------------------------
try {
  meter();
  const colsOnly = toArrow(await file.read({ columns: ['x', 'y', 'feature_name'] }));
  const colStats = meter();
  const got = names(colsOnly);
  check(
    'columns alone projects the schema',
    got.length === 3 && got.every((n) => ['x', 'y', 'feature_name'].includes(n)),
    `schema = [${got.join(', ')}], ${colsOnly.numRows} rows, ${(colStats.bytes / 1024).toFixed(1)} KiB`
  );
} catch (e) {
  check('columns alone projects the schema', false, `${e.name}: ${e.message}`);
}

// --- 3. columns + rowGroups together, which is what Celldega needs -----------
let projected = null;
try {
  meter();
  projected = toArrow(
    await file.read({ rowGroups: [RG], columns: ['x', 'y', 'feature_name'] })
  );
  const projStats = meter();
  const got = names(projected);
  check(
    'columns + rowGroups projects the schema',
    got.length === 3,
    `schema = [${got.join(', ')}]`
  );
  check(
    'row count matches the selected row group',
    projected.numRows === EXPECTED_ROWS,
    `${projected.numRows} rows (expected ${EXPECTED_ROWS})`
  );
  console.log(
    `        fetched ${(projStats.bytes / 1024).toFixed(1)} KiB in ${projStats.requests} request(s)`
  );

  // --- 4. values are actually correct, not just structurally decodable -------
  let valuesOk = true;
  const detail = [];
  for (const [column, expected] of Object.entries(EXPECTED_FIRST)) {
    const child = projected.getChild(column);
    if (!child) {
      valuesOk = false;
      detail.push(`${column}: missing`);
      continue;
    }
    for (let i = 0; i < expected.length; i += 1) {
      const actual = child.get(i);
      const value = typeof actual === 'number' ? actual : String(actual);
      const same =
        typeof expected[i] === 'number'
          ? Math.abs(value - expected[i]) < 1e-6
          : value === expected[i];
      if (!same) {
        valuesOk = false;
        detail.push(`${column}[${i}] = ${value}, expected ${expected[i]}`);
      }
    }
  }
  check('values match pyarrow', valuesOk, detail.join('; ') || 'first 3 rows of each column');
} catch (e) {
  check('columns + rowGroups projects the schema', false, `${e.name}: ${e.message}`);
}

// --- 5. does projection actually fetch less? --------------------------------
meter();
await file.read({ rowGroups: [RG] });
const fullStats = meter();
meter();
await file.read({ rowGroups: [RG], columns: ['x', 'y', 'feature_name'] });
const thinStats = meter();
check(
  'projection fetches fewer bytes than a full read',
  thinStats.bytes < fullStats.bytes,
  `${(thinStats.bytes / 1024).toFixed(1)} KiB projected vs ${(fullStats.bytes / 1024).toFixed(1)} KiB full ` +
    `(${((1 - thinStats.bytes / fullStats.bytes) * 100).toFixed(0)}% saved)`
);

// --- 6. the documented caveat: the sync reader ignores `columns` -------------
try {
  const response = await realFetch(URL_);
  const buf = new Uint8Array(await response.arrayBuffer());
  const sync = toArrow(pq.readParquet(buf, { columns: ['x', 'y'] }));
  const got = names(sync);
  check(
    'sync readParquet ignores columns (known caveat)',
    got.length > 2,
    `returned ${got.length} columns, so the caveat holds -- use ParquetFile.read`
  );
} catch (e) {
  check('sync readParquet ignores columns (known caveat)', false, `${e.name}: ${e.message}`);
}

const failed = results.filter((r) => !r.ok);
console.log(
  `\n${results.length - failed.length}/${results.length} checks passed` +
    (failed.length ? `; failed: ${failed.map((f) => f.name).join(', ')}` : '')
);
process.exit(failed.length ? 1 : 0);
