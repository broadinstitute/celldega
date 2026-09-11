/**
 * Report, in the browser console, whether parquet-wasm column projection actually works.
 *
 * Upstream 0.7.x paired correctly projected record batches with the *unprojected* schema,
 * so the Arrow IPC buffer was malformed and Arrow JS threw while decoding
 * (kylebarron/parquet-wasm#810). The experimental fork carries the fix from PR #811.
 *
 * The question this answers is narrower than "is the upstream bug fixed": it is whether
 * projection works against the apache-arrow version *this bundle* ships, on a real file
 * served the way the viewer serves it. Those can differ, so the probe runs in place rather
 * than being inferred from a Node test.
 *
 * It reads one row group twice -- projected and full -- and prints the schema, row counts
 * and bytes fetched for each. Runs at most once per page.
 */

let announced = false;

/** Count bytes over a scoped set of fetches, so the two reads can be compared. */
const withByteMeter = async (fn) => {
  const real = globalThis.fetch;
  let bytes = 0;
  let requests = 0;
  globalThis.fetch = async (...args) => {
    const response = await real(...args);
    try {
      bytes += (await response.clone().arrayBuffer()).byteLength;
    } catch {
      /* opaque response; leave the count alone rather than guess */
    }
    requests += 1;
    return response;
  };
  try {
    const value = await fn();
    return { value, bytes, requests };
  } finally {
    globalThis.fetch = real;
  }
};

/**
 * @param {object} opts
 * @param {object} opts.parquetFile - an initialised parquet-wasm ParquetFile
 * @param {number} opts.rowGroup - a row group index known to hold rows
 * @param {string[]} opts.columns - columns to request
 * @param {string} opts.label - what is being read, for the log line
 * @param {Function} opts.toArrow - wasm table -> Arrow table
 */
export const probeColumnProjection = async ({
  parquetFile,
  rowGroup,
  columns,
  label,
  toArrow,
}) => {
  if (announced) return null;
  announced = true;

  const report = { label, rowGroup, requested: columns };

  try {
    const full = await withByteMeter(() =>
      parquetFile.read({ rowGroups: [rowGroup] })
    );
    const fullTable = toArrow(full.value);
    report.fullColumns = fullTable.schema.fields.map((f) => f.name);
    report.fullRows = fullTable.numRows;
    report.fullBytes = full.bytes;

    const thin = await withByteMeter(() =>
      parquetFile.read({ rowGroups: [rowGroup], columns })
    );
    const thinTable = toArrow(thin.value);
    report.gotColumns = thinTable.schema.fields.map((f) => f.name);
    report.thinRows = thinTable.numRows;
    report.thinBytes = thin.bytes;

    const projected =
      report.gotColumns.length === columns.length &&
      columns.every((c) => report.gotColumns.includes(c));
    const rowsMatch = report.thinRows === report.fullRows;
    report.ok = projected && rowsMatch;

    const kib = (n) => `${(n / 1024).toFixed(1)} KiB`;
    // A file holding only the requested columns has nothing to skip, so 0% is the correct
    // answer rather than a disappointing one. Saying so avoids reading it as a failure.
    const nothingToSkip =
      report.fullColumns.length === report.gotColumns.length;
    const saved = nothingToSkip
      ? 'file has no other columns, so nothing to skip'
      : report.fullBytes > 0
        ? `${((1 - report.thinBytes / report.fullBytes) * 100).toFixed(0)}% fewer bytes`
        : 'byte count unavailable';

    /* eslint-disable no-console */
    console.log(
      `%c[parquet-wasm projection]%c ${report.ok ? 'WORKS' : 'BROKEN'} on ${label}`,
      'font-weight:bold',
      'font-weight:normal'
    );
    console.log(
      `  requested [${columns.join(', ')}] -> got [${report.gotColumns.join(', ')}]`
    );
    console.log(
      `  full read : ${report.fullColumns.length} columns, ${report.fullRows} rows, ${kib(report.fullBytes)}`
    );
    console.log(
      `  projected : ${report.gotColumns.length} columns, ${report.thinRows} rows, ${kib(report.thinBytes)} (${saved})`
    );
    if (!projected) {
      console.warn(
        '  schema was not projected -- the reader is falling back to full reads'
      );
    } else if (!rowsMatch) {
      console.warn(
        `  row count changed under projection (${report.thinRows} vs ${report.fullRows})`
      );
    }
    /* eslint-enable no-console */
  } catch (error) {
    report.ok = false;
    report.error = `${error.name}: ${error.message}`;
    // eslint-disable-next-line no-console
    console.warn(
      `[parquet-wasm projection] threw on ${label}: ${report.error} -- falling back to full reads`
    );
  }

  if (typeof window !== 'undefined') {
    window.celldega_projection_probe = report;
  }
  return report;
};

/** Allow a second probe, for tests. */
export const resetProjectionProbe = () => {
  announced = false;
};
