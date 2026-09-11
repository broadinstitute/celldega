import { execSync } from 'child_process';
import { readFileSync } from 'fs';
import esbuild from 'esbuild';
import fs from 'fs/promises';
import path from 'path';
import wasmPlugin from './wasm-plugin.mjs';

const isWatchMode = process.argv.includes('--watch');

/**
 * Stamp the bundle with the branch and commit it was built from.
 *
 * anywidget serves the published CDN bundle for a clean X.Y.Z version unless
 * CELLDEGA_LOCAL_ESM is set, so "am I running my own build?" is a real and easy question
 * to get wrong -- it has cost a debugging session before. The answer is now in the console.
 */
function buildStamp() {
  const git = (cmd) => {
    try {
      return execSync(cmd, {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      }).trim();
    } catch {
      return 'unknown';
    }
  };
  // The resolved parquet-wasm identity, not the range in package.json. An npm alias means
  // the installed package can be a fork under the same import name, and "is the fork
  // actually loaded, or a cached upstream build?" is otherwise guesswork.
  let parquetWasm = 'unknown';
  try {
    const meta = JSON.parse(
      readFileSync('node_modules/parquet-wasm/package.json', 'utf8')
    );
    parquetWasm = `${meta.name}@${meta.version}`;
  } catch {
    /* leave it unknown rather than assert something false */
  }

  return {
    branch: git('git rev-parse --abbrev-ref HEAD'),
    commit: git('git rev-parse --short HEAD'),
    dirty: git('git status --porcelain') !== '',
    parquetWasm,
    built: new Date().toISOString(),
  };
}

async function main() {
  try {
    const srcPath = path.resolve('src/celldega/static/celldega.js');
    const destPath = path.resolve('docs/assets/js/celldega.js');

    const context = await esbuild.context({
      entryPoints: ['js/celldega.js'],
      bundle: true,
      minify: true,
      target: ['es2020'],
      plugins: [wasmPlugin],
      outdir: 'src/celldega/static',
      format: 'esm',
      define: {
        'define.amd': 'false',
        __CELLDEGA_BUILD__: JSON.stringify(buildStamp()),
      },
      metafile: true,
    });

    if (isWatchMode) {
      // ✅ Build once, copy assets, then watch
      await context.watch();
      console.log('Watch mode enabled. Listening for changes...');
    } else {
      const result = await context.rebuild();
      console.log('Build succeeded:', result);

      // Copy widget.js
      console.log(`Copying ${srcPath} to ${destPath}...`);
      await fs.mkdir(path.dirname(destPath), { recursive: true });
      await fs.copyFile(srcPath, destPath);
      console.log('File copied successfully.');

      // Write metadata
      const metadataPath = path.resolve('meta.json');
      await fs.writeFile(
        metadataPath,
        JSON.stringify(result.metafile, null, 2)
      );
      console.log(`Metadata written to ${metadataPath}`);

      await context.dispose();
      process.exit(0);
    }

    process.on('exit', async () => {
      await context.dispose();
    });
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1);
  }
}

main();
