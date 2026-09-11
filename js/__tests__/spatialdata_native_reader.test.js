/**
 * Reading cell/gene metadata and expression straight out of a SpatialData Zarr store.
 *
 * The pieces pinned here are the ones whose failure is silent in the browser:
 *
 *  - `feature_code` must equal the row position, or transcripts get the wrong colours;
 *  - the `geometry` column must be a real Arrow List, or `get_scatter_data` reads nothing;
 *  - a manifest with no `spatialdata` block must leave DegaFiles completely alone;
 *  - a coordinate transform that cannot be reduced must raise, not silently drop rotation.
 *
 * The adapter's network path is covered separately by scripts/validate_spatialdata_reader.mjs,
 * which runs against a real store.
 */

/* global require */

const loadModule = (relativePath, exportNames, stubs = {}) => {
  const fs = require('fs');
  const path = require('path');

  let source = fs.readFileSync(path.join(__dirname, relativePath), 'utf8');

  // The suite has no babel transform, so ESM syntax is rewritten by hand, the way the
  // other tests in this directory do it.
  source = source
    .replace(/^import \* as (\w+) from '([^']+)';$/gm, (_, name, mod) =>
      Object.prototype.hasOwnProperty.call(stubs, mod)
        ? `const ${name} = stubs[${JSON.stringify(mod)}];`
        : `const ${name} = require('${mod}');`
    )
    .replace(/^import \{[^}]*\} from '[^']+';$/gm, '')
    .replace(/^import \w+ from '[^']+';$/gm, '')
    .replace(/^export const /gm, 'const ')
    .replace(/^export class /gm, 'class ')
    .replace(/^export \{[^}]*\};$/gm, '');

  const code = `${source}\nmodule.exports = { ${exportNames.join(', ')} };`;
  const module = { exports: {} };
  new Function('module', 'exports', 'stubs', 'require', code)(
    module,
    module.exports,
    stubs,
    require
  );
  return module.exports;
};

describe('CSR gene-major access', () => {
  let geneColumn;
  let geneStats;

  beforeAll(() => {
    ({ geneColumn, geneStats } = loadModule('../spatialdata/csr.js', [
      'geneColumn',
      'geneStats',
    ]));
  });

  // 4 cells x 3 genes:
  //   cell0: g0=1, g2=5
  //   cell1: g1=2
  //   cell2: (empty)
  //   cell3: g0=3, g1=4
  const csr = {
    data: Float32Array.from([1, 5, 2, 3, 4]),
    indices: Int32Array.from([0, 2, 1, 0, 1]),
    indptr: Int32Array.from([0, 2, 3, 3, 5]),
    shape: [4, 3],
  };

  test('reads a gene column including its zeros', () => {
    expect(Array.from(geneColumn(csr, 0))).toEqual([1, 0, 0, 3]);
    expect(Array.from(geneColumn(csr, 1))).toEqual([0, 2, 0, 4]);
    expect(Array.from(geneColumn(csr, 2))).toEqual([5, 0, 0, 0]);
  });

  test('handles a gene absent from every cell', () => {
    const empty = { ...csr, shape: [4, 4] };
    expect(Array.from(geneColumn(empty, 3))).toEqual([0, 0, 0, 0]);
  });

  test('statistics count the zero cells in the denominator', () => {
    const { mean, std, max, nonZero } = geneStats(csr);

    // gene 0: values [1, 0, 0, 3] -> mean 1, E[x^2] = 10/4 = 2.5, var = 1.5
    expect(mean[0]).toBeCloseTo(1, 10);
    expect(max[0]).toBe(3);
    expect(nonZero[0]).toBeCloseTo(0.5, 10);
    expect(std[0]).toBeCloseTo(Math.sqrt(1.5), 10);

    // gene 2: values [5, 0, 0, 0]
    expect(mean[2]).toBeCloseTo(1.25, 10);
    expect(max[2]).toBe(5);
    expect(nonZero[2]).toBeCloseTo(0.25, 10);
  });
});

describe('DegaFiles-shaped Arrow tables', () => {
  let tables;
  let accessors;

  beforeAll(() => {
    tables = loadModule(
      '../spatialdata/dega_tables.js',
      [
        'buildMetaGeneTable',
        'buildCellMetadataTable',
        'buildClusterTable',
        'buildMetaClusterTable',
        'defaultGeneColors',
      ],
      {}
    );
    accessors = loadModule('../read_parquet/table_accessors.js', [
      'getRowKeyArray',
      'getTableColumnArray',
    ]);
  });

  test('meta_gene table matches what set_meta_gene reads', () => {
    const table = tables.buildMetaGeneTable({
      names: ['GENEA', 'GENEB', 'GENEC'],
      mean: [1, 2, 3],
      std: [0.1, 0.2, 0.3],
      max: [10, 20, 30],
      nonZero: [0.5, 0.6, 0.7],
      colors: ['#aabbcc', '#ddeeff', '#010203'],
    });

    // set_meta_gene reads the index this exact way.
    expect(
      accessors.getRowKeyArray(table, ['__index_level_0__'], {
        fallbackToRangeIndex: false,
      })
    ).toEqual(['GENEA', 'GENEB', 'GENEC']);
    expect(accessors.getTableColumnArray(table, 'mean')).toEqual([1, 2, 3]);
    expect(accessors.getTableColumnArray(table, 'color')).toEqual([
      '#aabbcc',
      '#ddeeff',
      '#010203',
    ]);
  });

  test('feature_code equals row position', () => {
    const n = 50;
    const table = tables.buildMetaGeneTable({
      names: Array.from({ length: n }, (_, i) => `G${i}`),
      mean: new Array(n).fill(0),
      std: new Array(n).fill(0),
      max: new Array(n).fill(0),
      nonZero: new Array(n).fill(0),
    });

    // The transcript layer colours by g_colorMapping_inv[feature_code], so any drift here
    // silently mis-colours every point.
    const codes = accessors.getTableColumnArray(table, 'feature_code');
    expect(codes).toEqual(Array.from({ length: n }, (_, i) => i));
  });

  test('cell_metadata geometry is readable by the get_scatter_data path', () => {
    const table = tables.buildCellMetadataTable({
      names: ['c0', 'c1', 'c2'],
      centroids: Float64Array.from([1, 2, 3, 4, 5, 6]),
    });

    // Exactly what get_scatter_data does.
    const geometryColumn = table.getChild('geometry')?.getChildAt(0);
    const chunks = geometryColumn?.data?.map((x) => x.values) || [];
    const total = chunks.reduce((acc, c) => acc + c.length, 0);
    const flat = new Float64Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      flat.set(chunk, offset);
      offset += chunk.length;
    }

    expect(flat.length / table.numRows).toBe(2);
    expect(Array.from(flat)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(accessors.getTableColumnArray(table, 'name')).toEqual([
      'c0',
      'c1',
      'c2',
    ]);
  });

  test('cluster tables carry counts and a colour per group', () => {
    const clusters = ['a', 'b', 'a', 'a'];
    const clusterTable = tables.buildClusterTable({
      cellNames: ['c0', 'c1', 'c2', 'c3'],
      clusters,
    });
    expect(accessors.getTableColumnArray(clusterTable, 'cluster')).toEqual(
      clusters
    );

    const metaCluster = tables.buildMetaClusterTable({
      clusters,
      palette: { a: '#111111' },
    });
    expect(metaCluster.numRows).toBe(2);
    const names = accessors.getRowKeyArray(metaCluster, ['__index_level_0__'], {
      fallbackToRangeIndex: false,
    });
    const counts = accessors
      .getTableColumnArray(metaCluster, 'count')
      .map(Number);
    expect(Object.fromEntries(names.map((n, i) => [n, counts[i]]))).toEqual({
      a: 3,
      b: 1,
    });
    // A supplied palette wins; the rest are generated.
    const colors = accessors.getTableColumnArray(metaCluster, 'color');
    expect(colors[names.indexOf('a')]).toBe('#111111');
    expect(colors[names.indexOf('b')]).toMatch(/^#[0-9a-f]{6}$/);
  });

  test('fallback gene colours are deterministic and valid hex', () => {
    const a = tables.defaultGeneColors(16);
    const b = tables.defaultGeneColors(16);
    expect(a).toEqual(b);
    expect(a).toHaveLength(16);
    a.forEach((c) => expect(c).toMatch(/^#[0-9a-f]{6}$/));
    // Golden-ratio stepping should not repeat a colour this early.
    expect(new Set(a).size).toBe(16);
  });
});

describe('coordinate transform reduction', () => {
  let reduceTransform;

  beforeAll(() => {
    ({ reduceTransform } = loadModule(
      '../spatialdata/spatialdata_store.js',
      ['reduceTransform'],
      { zarrita: {} }
    ));
  });

  test('identity and missing transforms are the identity', () => {
    expect(reduceTransform(null)).toEqual({
      scale: [1, 1],
      translation: [0, 0],
    });
    expect(reduceTransform({ type: 'identity' })).toEqual({
      scale: [1, 1],
      translation: [0, 0],
    });
  });

  test('scale is picked out by axis name, not position', () => {
    // Points carry a z axis, so blindly taking scale[0], scale[1] would still work here --
    // but for an element declared ["y", "x"] it would silently transpose the image.
    expect(
      reduceTransform({ type: 'scale', scale: [2, 3, 1] }, ['x', 'y', 'z'])
    ).toEqual({ scale: [2, 3], translation: [0, 0] });
    expect(
      reduceTransform({ type: 'scale', scale: [2, 3] }, ['y', 'x'])
    ).toEqual({ scale: [3, 2], translation: [0, 0] });
  });

  test('the Xenium micron-to-pixel scale round-trips', () => {
    const s = 4.705882352941177;
    const { scale } = reduceTransform({ type: 'scale', scale: [s, s] }, [
      'x',
      'y',
    ]);
    expect(scale[0] * 446.3266906738281).toBeCloseTo(2100.36, 2);
  });

  test('a sequence composes in order', () => {
    const composed = reduceTransform(
      {
        type: 'sequence',
        transformations: [
          { type: 'scale', scale: [2, 2] },
          { type: 'translation', translation: [10, 20] },
        ],
      },
      ['x', 'y']
    );
    expect(composed).toEqual({ scale: [2, 2], translation: [10, 20] });

    // Order matters: translating before scaling scales the translation too.
    const reversed = reduceTransform(
      {
        type: 'sequence',
        transformations: [
          { type: 'translation', translation: [10, 20] },
          { type: 'scale', scale: [2, 2] },
        ],
      },
      ['x', 'y']
    );
    expect(reversed).toEqual({ scale: [2, 2], translation: [20, 40] });
  });

  test('an unreducible transform raises instead of dropping rotation', () => {
    expect(() =>
      reduceTransform({ type: 'affine', affine: [[0, -1, 0]] })
    ).toThrow(/not supported/);
  });
});

describe('manifest opt-in', () => {
  let spatialDataOptionsFromManifest;
  let resolveStoreUrl;

  beforeAll(() => {
    ({ spatialDataOptionsFromManifest, resolveStoreUrl } = loadModule(
      '../spatialdata/manifest_options.js',
      ['spatialDataOptionsFromManifest', 'resolveStoreUrl']
    ));
  });

  test('a DegaFiles manifest opts out by having no block', () => {
    expect(spatialDataOptionsFromManifest({}, 'https://host/dega')).toBeNull();
    expect(
      spatialDataOptionsFromManifest(
        { technology: 'Xenium' },
        'https://host/dega'
      )
    ).toBeNull();
  });

  test('a relative store_url resolves against the profile directory', () => {
    const base = 'https://host/data/sample.zarr/visualization/grid_files_v1';
    expect(resolveStoreUrl(base, '../..')).toBe(
      'https://host/data/sample.zarr'
    );
    expect(resolveStoreUrl(base, 'https://elsewhere/x.zarr')).toBe(
      'https://elsewhere/x.zarr'
    );
  });

  test('.. cannot escape past the origin', () => {
    expect(resolveStoreUrl('https://host', '../../../..')).toBe('https://host');
  });

  test('defaults fill in when the block is minimal', () => {
    const opts = spatialDataOptionsFromManifest(
      { spatialdata: {} },
      'https://host/s.zarr/visualization/grid_files_v1'
    );
    expect(opts.storeUrl).toBe('https://host/s.zarr');
    expect(opts.table).toBe('table');
    expect(opts.centroidKey).toBe('spatial');
    expect(opts.clusterColumn).toBeNull();
    expect([...opts.native].sort()).toEqual(['cbg', 'images', 'metadata']);
  });

  test('unknown components are ignored rather than trusted', () => {
    const opts = spatialDataOptionsFromManifest(
      { spatialdata: { native: ['metadata', 'images', 'nonsense'] } },
      'https://host/s.zarr/visualization/grid_files_v1'
    );
    expect([...opts.native]).toEqual(['metadata', 'images']);
  });
});

describe('control features', () => {
  let spatialDataOptionsFromManifest;

  beforeAll(() => {
    ({ spatialDataOptionsFromManifest } = loadModule(
      '../spatialdata/manifest_options.js',
      ['spatialDataOptionsFromManifest']
    ));
  });

  test('the feature catalog is carried through from the manifest', () => {
    // feature_code indexes genes-then-controls, but `var` holds only the genes. Xenium
    // pancreas reaches code 539 against 377 genes, so without this the control
    // transcripts index past the end of the colour table and silently lose their colour.
    const opts = spatialDataOptionsFromManifest(
      {
        spatialdata: {},
        feature_catalog: {
          n_genes: 377,
          extra_features: ['NegControlProbe_00042', 'UnassignedCodeword_0001'],
        },
      },
      'https://host/s.zarr/visualization/grid_files_v1'
    );
    expect(opts.featureCatalog.n_genes).toBe(377);
    expect(opts.featureCatalog.extra_features).toHaveLength(2);
  });

  test('a manifest without one is still fine', () => {
    const opts = spatialDataOptionsFromManifest(
      { spatialdata: {} },
      'https://host/s.zarr/visualization/grid_files_v1'
    );
    expect(opts.featureCatalog).toBeNull();
  });
});

describe('categorical palettes', () => {
  let categoricalPalette;

  beforeAll(() => {
    ({ categoricalPalette } = loadModule('../spatialdata/adapter.js', [
      'categoricalPalette',
    ]));
  });

  test('uses stored category order, including unused categories', () => {
    expect(
      categoricalPalette(
        ['B', 'A', 'unused'],
        ['#ff0000', '#00ff00', '#0000ff']
      )
    ).toEqual({ B: '#ff0000', A: '#00ff00', unused: '#0000ff' });
  });
});

describe('gene colour palette padding', () => {
  let tables;

  beforeAll(() => {
    tables = loadModule(
      '../spatialdata/dega_tables.js',
      ['buildMetaGeneTable', 'defaultGeneColors'],
      {}
    );
  });

  test('a short colour array would break the table, so it must be padded', () => {
    // uns["gene_colors"] covers genes only (377 for Xenium pancreas) while the gene list
    // includes controls (541). Arrow rejects mismatched column lengths outright.
    const names = ['G0', 'G1', 'CTRL0', 'CTRL1'];
    const fromVar = ['#111111', '#222222'];
    const fallback = tables.defaultGeneColors(names.length);
    const padded = names.map((_, i) => fromVar[i] ?? fallback[i]);

    const table = tables.buildMetaGeneTable({
      names,
      mean: [0, 0, 0, 0],
      std: [0, 0, 0, 0],
      max: [0, 0, 0, 0],
      nonZero: [0, 0, 0, 0],
      colors: padded,
      isGene: [true, true, false, false],
    });

    expect(table.numRows).toBe(4);
    expect(table.getChild('color').get(0)).toBe('#111111');
    expect(table.getChild('color').get(2)).toMatch(/^#[0-9a-f]{6}$/);
    expect(table.getChild('is_gene').get(2)).toBe(false);
  });
});
