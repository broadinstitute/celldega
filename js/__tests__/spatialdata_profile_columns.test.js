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

  const source = fs
    .readFileSync(
      path.join(__dirname, '../read_parquet/row_group_tile_reader.js'),
      'utf8'
    )
    .replace(/^import[\s\S]*?;$/gm, '')
    .replace(/^export default [\s\S]*?;$/gm, '')
    .replace(/^export /gm, '');
  const code = `${source}\nmodule.exports = { RowGroupTileReader };`;
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
  columns: ['display_xy', 'feature_code'],
});

describe('RowGroupTileReader column projection', () => {
  test('DegaFiles config requests no projection', () => {
    const reader = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      degaFilesConfig()
    );
    expect(reader.columns).toBeNull();
    expect(reader._readOptions([0, 1])).toEqual({ rowGroups: [0, 1] });
  });

  test('SpatialData config forwards columns to ParquetFile.read', () => {
    const reader = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      spatialDataConfig()
    );
    expect(reader.columns).toEqual(['display_xy', 'feature_code']);
    expect(reader._readOptions([5])).toEqual({
      rowGroups: [5],
      columns: ['display_xy', 'feature_code'],
    });
  });

  test('an empty columns array is treated as no projection', () => {
    const reader = new RowGroupTileReader('http://x', TILE_GRID, {
      ...degaFilesConfig(),
      columns: [],
    });
    expect(reader.columns).toBeNull();
  });

  test('legacy single-file string config still works', () => {
    const reader = new RowGroupTileReader('http://x', TILE_GRID, 'trx.parquet');
    expect(reader.columns).toBeNull();
    expect(reader.url).toBe('http://x/trx.parquet');
  });

  test('projection is part of the read cache identity', () => {
    const plain = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      degaFilesConfig()
    );
    const projected = new RowGroupTileReader(
      'http://x',
      TILE_GRID,
      spatialDataConfig()
    );
    const key = (r) =>
      `table:${r.columns ? r.columns.join('+') : 'all'}:${[1, 2].join(',')}`;
    expect(key(plain)).not.toEqual(key(projected));
  });

  test('relative directories resolve into a SpatialData store', () => {
    // The manifest lives in the profile directory and points back into the store,
    // so Celldega needs no knowledge of the zarr layout.
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
    // Resolved the way fetch() would, so the '../..' segments are collapsed.
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
