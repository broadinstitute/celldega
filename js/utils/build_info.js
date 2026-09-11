/**
 * Which build is actually running.
 *
 * anywidget resolves a clean `X.Y.Z` install to the published jsDelivr bundle, so local
 * `js/` edits silently do nothing unless CELLDEGA_LOCAL_ESM is set. That failure mode is
 * invisible -- the viewer works, it is just running someone else's code -- and it has cost
 * a full debugging session before. Printing the branch and commit makes it a one-glance
 * check instead of an investigation.
 */

/* global __CELLDEGA_BUILD__ */

// Replaced at bundle time by esbuild's `define`. The fallback covers running the sources
// directly (tests, node scripts), where no build has happened.
const STAMP =
  typeof __CELLDEGA_BUILD__ !== 'undefined'
    ? __CELLDEGA_BUILD__
    : {
        branch: 'source',
        commit: 'unbundled',
        dirty: false,
        parquetWasm: 'unknown',
        built: null,
      };

export const buildInfo = STAMP;

let announced = false;

/** Print the build stamp once per page, whatever else is going on. */
export const announceBuild = (extra = null) => {
  if (announced) return STAMP;
  announced = true;

  const dirty = STAMP.dirty ? ' +local-changes' : '';
  const when = STAMP.built ? ` built ${STAMP.built}` : '';
  const pw = STAMP.parquetWasm
    ? `\n           parquet-wasm ${STAMP.parquetWasm}`
    : '';
  // eslint-disable-next-line no-console
  console.log(
    `%c[celldega]%c ${STAMP.branch}@${STAMP.commit}${dirty}${when}${extra ? ` — ${extra}` : ''}${pw}`,
    'font-weight:bold',
    'font-weight:normal'
  );

  return STAMP;
};
