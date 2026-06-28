// wasm-plugin.mjs
import path from 'node:path';
import fs from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

let wasmPlugin = {
  name: 'wasm',
  setup(build) {
    build.onResolve({ filter: /\.wasm$/ }, (args) => {
      if (args.resolveDir === '') {
        return; // Ignore unresolvable paths
      }
      
      let resolvedPath;
      
      // Try to resolve from node_modules first
      if (!args.path.startsWith('.') && !args.path.startsWith('/')) {
        try {
          // For paths like 'parquet-wasm/esm/parquet_wasm_bg.wasm'
          resolvedPath = require.resolve(args.path);
        } catch (e) {
          // Fall back to relative resolution
          resolvedPath = path.join(args.resolveDir, args.path);
        }
      } else {
        resolvedPath = path.isAbsolute(args.path)
          ? args.path
          : path.join(args.resolveDir, args.path);
      }
      
      return {
        path: resolvedPath,
        namespace: 'wasm-binary',
      };
    });

    // Load WASM as binary data (Uint8Array)
    build.onLoad({ filter: /.*/, namespace: 'wasm-binary' }, async (args) => ({
      contents: await fs.promises.readFile(args.path),
      loader: 'binary',
    }));
  },
};

export default wasmPlugin;
