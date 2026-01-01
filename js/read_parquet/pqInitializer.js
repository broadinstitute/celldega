// Use parquet-wasm ESM with synchronous initialization from embedded WASM
import {
  initSync,
  readParquet,
  readSchema,
  ParquetFile,
} from 'parquet-wasm/esm/parquet_wasm.js';
import wasmBinary from 'parquet-wasm/esm/parquet_wasm_bg.wasm';

// Version from package.json
const PARQUET_WASM_VERSION = '0.7.1';

let initialized = false;

function ensureInitialized() {
  if (!initialized) {
    // wasmBinary is loaded as a Uint8Array by esbuild's wasm plugin
    // initSync accepts an ArrayBuffer or WebAssembly.Module
    initSync(wasmBinary);
    initialized = true;
    console.log(`[parquet-wasm] Initialized version ${PARQUET_WASM_VERSION}`);
  }
}

// Re-export parquet-wasm functions with auto-initialization
export async function getPq() {
  ensureInitialized();
  // Return an object with the same API as the old pq module
  return {
    readParquet,
    readSchema,
    ParquetFile,
    version: PARQUET_WASM_VERSION,
  };
}

/**
 * Read a parquet file with options (e.g., specific row groups)
 * @param {Uint8Array} data - Parquet file data
 * @param {Object} options - ReaderOptions: { rowGroups?: number[], columns?: string[], limit?: number, offset?: number }
 * @returns {Table} - Arrow Table in WASM memory
 */
export function readParquetWithOptions(data, options = {}) {
  ensureInitialized();
  return readParquet(data, options);
}

/**
 * Get the parquet-wasm version
 */
export function getVersion() {
  return PARQUET_WASM_VERSION;
}
