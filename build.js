import esbuild from 'esbuild';
import fs from 'fs/promises';
import path from 'path';
import wasmPlugin from './wasm-plugin.mjs';

const isWatchMode = process.argv.includes('--watch');

// Plugin that prints on the console when a build is starting, errors, and completed.
const watchPlugin = {
  name: 'watch-plugin',
  setup(build) {
    build.onStart(() => {
      console.log((new Date).toString() + ': Build starting...');
    });
    build.onEnd((result) => {
      if (result.errors.length > 0) {
        console.error((new Date).toString() + ': Build failed with errors.');
      } else {
        console.log((new Date).toString() + ': Build successful.');
      }
    });
    console.log((new Date).toString() + ': Watch plugin has been setup.');
  },
};

async function main() {
  try {
    const srcPath = path.resolve('src/celldega/static/celldega.js');
    const destPath = path.resolve('docs/assets/js/celldega.js');

    const context = await esbuild.context({
      entryPoints: ['js/celldega.js'],
      bundle: true,
      minify: true,
      target: ['es2020'],
      plugins: [wasmPlugin, watchPlugin],
      outdir: 'src/celldega/static',
      format: 'esm',
      define: {
        'define.amd': 'false',
      },
      metafile: true,
      sourcemap: 'inline',
      sourcesContent: true,
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
