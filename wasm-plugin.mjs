// wasm-plugin.js
import * as esbuild from 'esbuild';
import path from 'node:path';
import fs from 'node:fs';

let wasmPlugin = {
  name: 'wasm',
  setup(build) {
    build.onResolve({ filter: /\.wasm$/ }, args => {
      if (args.namespace === 'wasm-stub') {
        return {
          path: args.path,
          namespace: 'wasm-binary',
        };
      }
      if (args.resolveDir === '') {
        return; // Ignore unresolvable paths
      }
      return {
        path: path.isAbsolute(args.path) ? args.path : path.join(args.resolveDir, args.path),
        namespace: 'wasm-stub',
      };
    });

    build.onLoad({ filter: /.*/, namespace: 'wasm-stub' }, async (args) => ({
      contents: `import wasm from ${JSON.stringify(args.path)}
export default (imports) =>
  WebAssembly.instantiate(wasm, imports).then(
    result => result.instance.exports)`,
    }));

    build.onLoad({ filter: /.*/, namespace: 'wasm-binary' }, async (args) => ({
      contents: await fs.promises.readFile(args.path),
      loader: 'binary',
    }));
  },
};

export default wasmPlugin;
