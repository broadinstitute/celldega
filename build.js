import esbuild from 'esbuild';
import fs from 'fs/promises';
import path from 'path';
import wasmPlugin from './wasm-plugin.mjs';

const isWatchMode = process.argv.includes('--watch');

async function main() {
  try {
    // Define paths
    const srcPath = path.resolve('src/celldega/static/widget.js');
    const destPath = path.resolve('docs/assets/js/widget.js');

    // Create a build context
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
      // Enable watch mode and listen for changes
      await context.watch();
      console.log("Watch mode enabled. Listening for changes...");
    } else {
      // Perform a single build if not in watch mode
      const result = await context.rebuild();
      console.log('Build succeeded:', result);

      // Copy widget.js to the docs/assets/js directory
      console.log(`Copying ${srcPath} to ${destPath}...`);
      await fs.mkdir(path.dirname(destPath), { recursive: true }); // Ensure destination directory exists
      await fs.copyFile(srcPath, destPath);
      console.log('File copied successfully.');

      // Write the metadata to a JSON file
      const metadataPath = path.resolve('meta.json');
      await fs.writeFile(metadataPath, JSON.stringify(result.metafile, null, 2));
      console.log(`Metadata written to ${metadataPath}`);

      // Dispose of the context after a successful build to ensure the process exits
      await context.dispose();
      process.exit(0); // Exit successfully
    }

    // Handle clean up for watch mode on process exit
    process.on('exit', async () => {
      await context.dispose();
    });
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1); // Exit with error
  }
}

main();
