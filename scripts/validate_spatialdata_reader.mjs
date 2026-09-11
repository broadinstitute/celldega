// Inspect the SpatialData adapter against a real store. This diagnostic prints schemas,
// values and timings; it is not an assertion-based comparison or a browser rendering test.
//
//   python -m http.server 8896 --bind 127.0.0.1 --directory ../data
//   npx esbuild scripts/validate_spatialdata_reader.mjs --bundle --platform=node --format=esm --outfile=/tmp/v.mjs && node /tmp/v.mjs
import { SpatialDataAdapter } from '../js/spatialdata/adapter.js';
import { geneColumn } from '../js/spatialdata/csr.js';

const STORE = process.env.STORE ?? 'http://127.0.0.1:8896/pancreas_full.zarr';
const t = (label, ms) => `${label} (${ms} ms)`;

const adapter = new SpatialDataAdapter(STORE, {
  transformElement: 'shapes/cell_boundaries',
});

let t0 = Date.now();
const meta = await adapter.metaGeneTable();
console.log(t(`meta_gene table: ${meta.numRows} rows`, Date.now() - t0));
console.log(
  '  schema:',
  meta.schema.fields.map((f) => `${f.name}:${f.type}`).join(', ')
);

const names = meta.getChild('__index_level_0__').toArray();
const mean = meta.getChild('mean').toArray();
const std = meta.getChild('std').toArray();
const max = meta.getChild('max').toArray();
const nz = meta.getChild('non-zero').toArray();
const code = meta.getChild('feature_code').toArray();
console.log('  first 3 genes:');
for (let i = 0; i < 3; i += 1) {
  console.log(
    `    ${names[i]}  mean=${mean[i].toFixed(6)} std=${std[i].toFixed(6)} ` +
      `max=${max[i]} non-zero=${nz[i].toFixed(6)} feature_code=${code[i]}`
  );
}
console.log(
  '  feature_code == row position:',
  code.every((c, i) => c === i)
);

t0 = Date.now();
const cells = await adapter.cellMetadataTable();
console.log(t(`\ncell_metadata table: ${cells.numRows} rows`, Date.now() - t0));
console.log(
  '  schema:',
  cells.schema.fields.map((f) => `${f.name}:${f.type}`).join(', ')
);
// Exactly the access path get_scatter_data uses.
const geometry = cells.getChild('geometry')?.getChildAt(0);
const chunks = geometry?.data?.map((x) => x.values) ?? [];
const flat = chunks[0];
console.log(
  `  get_scatter_data path OK: ${chunks.length} chunk(s), size=${flat.length / cells.numRows}`
);
console.log(
  `  first 2 centroids: ${flat[0]}, ${flat[1]} / ${flat[2]}, ${flat[3]}`
);
console.log(`  first cell name: ${cells.getChild('name').get(0)}`);

t0 = Date.now();
const clusters = await adapter.clusterTable();
const metaClusters = await adapter.metaClusterTable();
console.log(
  t(
    `\ncluster tables: ${clusters.numRows} cells, ${metaClusters.numRows} groups`,
    Date.now() - t0
  )
);

t0 = Date.now();
const expr = await adapter.geneExpression(names[0]);
const nonZeroCount = expr.reduce((a, v) => a + (v !== 0 ? 1 : 0), 0);
console.log(
  t(
    `\ngene column "${names[0]}": ${expr.length} cells, ${nonZeroCount} non-zero`,
    Date.now() - t0
  )
);

// Timing for a warm random-gene fetch, which is what colouring by gene costs.
const csr = await adapter.store.csr();
t0 = Date.now();
for (let i = 0; i < 20; i += 1) geneColumn(csr, (i * 17) % names.length);
console.log(`  20 warm gene columns in ${Date.now() - t0} ms`);

// --- CBG path: what colouring by gene actually costs -------------------------
const { SpatialDataAdapter: A2 } = await import('../js/spatialdata/adapter.js');
const cold = new A2(STORE);
let c0 = Date.now();
await cold.store.csr();
console.log(`\ncold X fetch (whole matrix): ${Date.now() - c0} ms`);

c0 = Date.now();
const g1 = await cold.readGene(names[0]);
console.log(
  `  first readGene (warm X): ${Date.now() - c0} ms, ${g1.numRows} non-zero cells`
);

c0 = Date.now();
for (let i = 0; i < 20; i += 1)
  await cold.readGene(names[(i * 17) % names.length]);
console.log(`  20 sequential readGene : ${Date.now() - c0} ms total`);
