/**
 * The SpatialData regular-grid profile declares its own column names and a column
 * projection. These tests pin both halves of the contract:
 *
 *  - a DegaFiles dataset (which declares nothing) keeps reading `geometry` / `name`
 *    and keeps reading every column, exactly as before;
 *  - a SpatialData dataset reads `display_xy` / `feature_code` and projects.
 *
 * A regression in either direction is a silent failure in the browser, not a crash.
 */

/* global require */

// The suite has no babel transform, so source is loaded the way the other tests do it:
// read it, strip the ESM syntax, and evaluate. Only the class under test is needed, so
// its imports (which pull in parquet-wasm) are stripped too.
let RowGroupTileReader;

beforeAll(() => {
  const fs = require('fs');
  const path = require('path');

  const helper = fs
    .readFileSync(
      path.join(__dirname, '../read_parquet/normalize_base_url.js'),
      'utf8'
    )
    .replace(/^export default [\s\S]*?;$/gm, '')
    .replace(/^export /gm, '');
  const source = fs
    .readFileSync(
      path.join(__dirname, '../read_parquet/row_group_tile_reader.js'),
      'utf8'
    )
    .replace(/^import[\s\S]*?;$/gm, '')
    .replace(/^export default [\s\S]*?;$/gm, '')
    .replace(/^export /gm, '');
  const code = `${helper}\n${source}\nmodule.exports = { RowGroupTileReader };`;
  const module = { exports: {} };
  new Function('module', 'exports', code)(module, module.exports);
  ({ RowGroupTileReader } = module.exports);
});

const TILE_GRID = { num_tiles_x: 4, num_tiles_y: 3 };

const degaFilesConfig = () => ({
  directory: 'transcripts',
  files: ['chunk_0.parquet', 'chunk_1.parquet'],
  max_row_groups_per_file: 2,
  total_row_groups: 12,
});

const spatialDataConfig = () => ({
  ...degaFilesConfig(),
  position_column: 'display_xy',
  feature_column: 'feature_code',
});

describe('read options', () => {
  // Column projection was broken upstream (kylebarron/parquet-wasm#810): correctly
  // projected batches were paired with the unprojected schema, so tableFromIPC threw.
  // The experimental fork carries the PR #811 fix, so `columns` is requested again -- but
  // only when the caller declares them, and never after a failure.
  test('no projection is requested unless columns are declared', () => {
    for (const cfg of [degaFilesConfig(), spatialDataConfig()]) {
      const reader = new RowGroupTileReader('http://x', TILE_GRID, cfg);
      expect(reader._readOptions([0, 1])).toEqual({ rowGroups: [0, 1] });
      expect(reader._readOptions([0, 1])).not.toHaveProperty('columns');
    }
  });

  test('declared columns are requested', () => {
    const reader = new RowGroupTileReader('http://x', TILE_GRID, {
      ...spatialDataConfig(),
      columns: ['display_xy', 'feature_code'],
    });
    expect(reader._readOptions([5])).toEqual({
      rowGroups: [5],
      columns: ['display_xy', 'feature_code'],
    });
  });

  test('an empty columns array is treated as no declaration', () => {
    const reader = new RowGroupTileReader('http://x', TILE_GRID, {
      ...spatialDataConfig(),
      columns: [],
    });
    expect(reader._readOptions([5])).toEqual({ rowGroups: [5] });
  });

  test('a projection failure latches off for the rest of the session', () => {
    // Testing against an unreleased dependency, so a regression must degrade to slower
    // reads rather than a blank viewer.
    const reader = new RowGroupTileReader('http://x', TILE_GRID, {
      ...spatialDataConfig(),
      columns: ['display_xy'],
    });
    expect(reader._readOptions([5])).toHaveProperty('columns');
    reader.projectionBroken = true;
    expect(reader._readOptions([5])).toEqual({ rowGroups: [5] });
  });

  test('legacy single-file string config still works', () => {
    const reader = new RowGroupTileReader('http://x', TILE_GRID, 'trx.parquet');
    expect(reader.url).toBe('http://x/trx.parquet');
  });

  test('canonical single-file path config works', () => {
    const reader = new RowGroupTileReader('http://x/store.zarr', TILE_GRID, {
      path: 'shapes/cells/shapes.parquet',
      columns: ['geometry', 'cell_code'],
    });
    expect(reader.chunkedMode).toBe(false);
    expect(reader.url).toBe('http://x/store.zarr/shapes/cells/shapes.parquet');
    expect(reader.columns).toEqual(['geometry', 'cell_code']);
  });

  test('relative directories resolve into a SpatialData store', () => {
    const reader = new RowGroupTileReader(
      'http://x/store.zarr/visualization/prof',
      TILE_GRID,
      {
        ...spatialDataConfig(),
        directory: '../../points/transcripts/points.parquet',
      }
    );
    expect(reader.chunkedMode).toBe(true);
    const url = `${reader.baseUrl}/${reader.directory}/${reader.files[0]}`;
    const { URL: NodeURL } = require('url');
    expect(new NodeURL(url).pathname).toBe(
      '/store.zarr/points/transcripts/points.parquet/chunk_0.parquet'
    );
  });
});

describe('row group index formula', () => {
  test('matches tile_x * num_tiles_y + tile_y', () => {
    const reader = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      degaFilesConfig()
    );
    expect(reader.computeRowGroupIndex(0, 0)).toBe(0);
    expect(reader.computeRowGroupIndex(0, 2)).toBe(2);
    expect(reader.computeRowGroupIndex(1, 0)).toBe(3);
    expect(reader.computeRowGroupIndex(3, 2)).toBe(11);
  });

  test('chunk location splits by max_row_groups_per_file', () => {
    const reader = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      degaFilesConfig()
    );
    expect(reader.computeChunkLocation(0)).toEqual({
      fileIndex: 0,
      localIndex: 0,
    });
    expect(reader.computeChunkLocation(1)).toEqual({
      fileIndex: 0,
      localIndex: 1,
    });
    expect(reader.computeChunkLocation(2)).toEqual({
      fileIndex: 1,
      localIndex: 0,
    });
  });

  test('tiles outside the grid are rejected', () => {
    const reader = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      degaFilesConfig()
    );
    expect(reader.isValidTile(3, 2)).toBe(true);
    expect(reader.isValidTile(4, 0)).toBe(false);
    expect(reader.isValidTile(0, -1)).toBe(false);
  });
});

describe('base URL normalization', () => {
  // A base_url ending in '/' produces '//' when joined, which is an empty path segment.
  // That is harmless for a plain directory but silently eats one '..' from a relative
  // one, so a SpatialData store resolved to the wrong place and every tile 404'd.
  const RELATIVE = {
    directory: '../../points/transcripts/points.parquet',
    files: ['chunk_00.parquet', 'chunk_01.parquet'],
    max_row_groups_per_file: 400,
    total_row_groups: 800,
  };
  const resolve = (base) => {
    const r = new RowGroupTileReader(
      base,
      { num_tiles_x: 20, num_tiles_y: 40 },
      RELATIVE
    );
    const { URL: NodeURL } = require('url');
    return new NodeURL(`${r.baseUrl}/${r.directory}/${r.files[0]}`).pathname;
  };

  const EXPECTED = '/p.zarr/points/transcripts/points.parquet/chunk_00.parquet';

  test('resolves correctly without a trailing slash', () => {
    expect(resolve('http://h/p.zarr/visualization/grid')).toBe(EXPECTED);
  });

  test('resolves correctly with a trailing slash', () => {
    expect(resolve('http://h/p.zarr/visualization/grid/')).toBe(EXPECTED);
  });

  test('resolves correctly with several trailing slashes', () => {
    expect(resolve('http://h/p.zarr/visualization/grid///')).toBe(EXPECTED);
  });

  test('a plain directory is unaffected either way', () => {
    const plain = { ...RELATIVE, directory: 'transcripts' };
    const url = (base) =>
      new (require('url').URL)(
        `${new RowGroupTileReader(base, { num_tiles_x: 2, num_tiles_y: 2 }, plain).baseUrl}/transcripts/x.parquet`
      ).pathname;
    expect(url('http://h/dega/')).toBe('/dega/transcripts/x.parquet');
    expect(url('http://h/dega')).toBe('/dega/transcripts/x.parquet');
  });
});
