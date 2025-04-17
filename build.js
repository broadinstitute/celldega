import esbuild from 'esbuild';
import fs from 'fs/promises';
import path from 'path';
import wasmPlugin from './wasm-plugin.mjs';

const isWatchMode = process.argv.includes('--watch');

async function main() {
  try {
    const srcPath = path.resolve('src/celldega/static/widget.js');
    const destPath = path.resolve('docs/assets/js/widget.js');

    const context = await esbuild.context({
      entryPoints: ['js/widget.js'],
      bundle: true,
      minify: true,
      target: ['es2020'],
      plugins: [wasmPlugin],
      outdir: 'src/celldega/static',
      format: 'esm',
      define: {
        'define.amd': 'false',
      },
      metafile: true,
    });

    if (isWatchMode) {
      // ✅ Build once, copy assets, then watch
      await context.watch();
      console.log("Watch mode enabled. Listening for changes...");

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
      await fs.writeFile(metadataPath, JSON.stringify(result.metafile, null, 2));
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
