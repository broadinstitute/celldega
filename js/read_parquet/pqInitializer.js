// Use parquet-wasm ESM with synchronous initialization from embedded WASM
import { initSync, readParquet, readSchema } from 'parquet-wasm/esm/parquet_wasm.js';
import wasmBinary from 'parquet-wasm/esm/parquet_wasm_bg.wasm';

console.log('here')

let initialized = false;

function ensureInitialized() {
  if (!initialized) {
    // wasmBinary is loaded as a Uint8Array by esbuild's wasm plugin
    // initSync accepts an ArrayBuffer or WebAssembly.Module
    initSync(wasmBinary);
    initialized = true;
  }
}

// Re-export parquet-wasm functions with auto-initialization
export async function getPq() {
  ensureInitialized();
  // Return an object with the same API as the old pq module
  return {
    readParquet,
    readSchema,
  };
}
