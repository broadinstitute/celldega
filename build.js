// reference https://github.com/manzt/anywidget/issues/369
const esbuild = require('esbuild');

esbuild.build({
  entryPoints: ['js/widget.js'], // Adjusted for your entry file
  bundle: true,
  minify: true,
  target: ['es2020'],
  outdir: 'src/celldega/static', // Adjusted for your output directory
  format: 'esm',
  define: {
    'define.amd': 'false',
  },
}).catch(() => process.exit(1));
