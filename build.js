import esbuild from 'esbuild';
import wasmPlugin from './wasm-plugin.mjs';

const isWatchMode = process.argv.includes('--watch');

async function main() {
  try {
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
    });

    if (isWatchMode) {
      // Enable watch mode and listen for changes
      await context.watch();

      console.log("Watch mode enabled. Listening for changes...");

    } else {
      // Perform a single build if not in watch mode
      const result = await context.rebuild();
      console.log('Build succeeded:', result);

      // Dispose of the context after a successful build to ensure the process exits
      await context.dispose();
      process.exit(0); // Exit successfully
    }

    // Handle clean up for watch mode on process exit
    process.on('exit', () => {
      context.dispose();
    });
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1); // Exit with error
  }
}

main();
