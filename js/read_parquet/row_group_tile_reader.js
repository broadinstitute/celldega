/**
 * RowGroupTileReader - Efficient tile-based data access from row-grouped parquet files
 *
 * Supports both:
 * - Single file mode (legacy): one parquet file with all row groups
 * - Chunked mode: multiple parquet files, each with max N row groups
 *
 * Row group indices are computed using a simple formula:
 *   row_group_index = tile_x * num_tiles_y + tile_y
 *
 * For chunked mode:
 *   file_index = row_group_index // max_row_groups_per_file
 *   local_row_group_index = row_group_index % max_row_groups_per_file
 */

import * as arrow from 'apache-arrow';

import { concatenate_arrow_tables } from '../vector_tile/concatenate_functions';

import { normalizeBaseUrl } from './normalize_base_url';

import { getPq } from './pqInitializer';

/**
 * RowGroupTileReader class for efficient streaming tile-based data access
 */
export class RowGroupTileReader {
  /**
   * Create a new RowGroupTileReader
   * @param {string} baseUrl - Base URL for the landscape files
   * @param {Object} tileGrid - Grid dimensions { num_tiles_x, num_tiles_y }
   * @param {Object|string} fileConfig - Either a URL string (single file) or chunk config object
   */
  constructor(baseUrl, tileGrid, fileConfig) {
    // Tolerate a trailing slash: it would otherwise create an empty path segment that
    // absorbs one ".." from a relative directory, silently mis-resolving store paths.
    baseUrl = normalizeBaseUrl(baseUrl);
    this.baseUrl = baseUrl;
    this.numTilesX = tileGrid?.num_tiles_x || 0;
    this.numTilesY = tileGrid?.num_tiles_y || 0;
    this.initialized = false;
    this.requestCache = new Map();
    this.maxCachedReads = 4;

    // Determine mode: chunked or single file
    if (typeof fileConfig === 'string') {
      // Legacy single file mode
      this.chunkedMode = false;
      this.url = `${baseUrl}/${fileConfig}`;
      this.parquetFile = null;
    } else if (typeof fileConfig === 'object' && fileConfig.files) {
      // Check if we can use single-file mode (only 1 chunk file)
      if (fileConfig.files.length === 1) {
        // Use single-file mode for simplicity and better compatibility
        this.chunkedMode = false;
        this.url = `${baseUrl}/${fileConfig.directory}/${fileConfig.files[0]}`;
        this.parquetFile = null;
        // console.log(
        //   `[RowGroupTileReader] Single chunk file detected, using single-file mode`
        // );
      } else {
        // True chunked mode with multiple files
        this.chunkedMode = true;
        this.directory = fileConfig.directory;
        this.files = fileConfig.files;
        this.maxRowGroupsPerFile = fileConfig.max_row_groups_per_file || 10000;
        this.totalRowGroups = fileConfig.total_row_groups || 0;
      }
    } else {
      throw new Error(
        '[RowGroupTileReader] Invalid fileConfig: must be string URL or chunk config object'
      );
    }
  }

  _getCachedRead(cacheKey) {
    if (!this.requestCache.has(cacheKey)) {
      return null;
    }

    const cachedRead = this.requestCache.get(cacheKey);
    this.requestCache.delete(cacheKey);
    this.requestCache.set(cacheKey, cachedRead);
    return cachedRead;
  }

  _setCachedRead(cacheKey, readPromise) {
    this.requestCache.set(cacheKey, readPromise);

    while (this.requestCache.size > this.maxCachedReads) {
      const oldestKey = this.requestCache.keys().next().value;
      this.requestCache.delete(oldestKey);
    }

    return readPromise;
  }

  /**
   * Build the parquet-wasm read options.
   *
   * Deliberately no column projection: passing `columns` to ParquetFile.read corrupts
   * the IPC stream parquet-wasm emits, so tableFromIPC then throws. Reproduced on
   * parquet-wasm 0.7.1 and 0.7.2 with apache-arrow 15 and 18, for scalar and nested
   * columns alike, and even with an empty `columns` array.
   *
   * Projection is unnecessary anyway: a SpatialData profile puts its render columns in
   * their own file, so reading every column of that file already transfers only what is
   * needed.
   *
   * @param {Array<number>} rowGroups - Row group indices local to the file being read
   * @returns {{rowGroups: Array<number>}}
   */
  _readOptions(rowGroups) {
    return { rowGroups };
  }

  async _readRowGroups(uniqueIndices, options = {}) {
    const returnTablesArray = options.returnTablesArray === true;

    if (!this.chunkedMode) {
      const wasmTable = await this.parquetFile.read(
        this._readOptions(uniqueIndices)
      );
      const arrowIPC = wasmTable.intoIPCStream();
      const table = arrow.tableFromIPC(arrowIPC);
      return returnTablesArray ? [table] : table;
    }

    const byFile = new Map();
    for (const globalIndex of uniqueIndices) {
      const { fileIndex, localIndex } = this.computeChunkLocation(globalIndex);
      if (!byFile.has(fileIndex)) {
        byFile.set(fileIndex, []);
      }
      byFile.get(fileIndex).push(localIndex);
    }

    const tables = await Promise.all(
      [...byFile.entries()].map(async ([fileIndex, localIndices]) => {
        const pqFile = await this._getParquetFile(fileIndex);
        const wasmTable = await pqFile.read(this._readOptions(localIndices));
        const arrowIPC = wasmTable.intoIPCStream();
        return arrow.tableFromIPC(arrowIPC);
      })
    );

    if (tables.length === 0) {
      return null;
    }

    if (returnTablesArray) {
      return tables;
    }

    if (tables.length === 1) {
      return tables[0];
    }

    return concatenate_arrow_tables(tables);
  }

  /**
   * Compute the row group index from tile coordinates using the formula:
   *   row_group_index = tile_x * num_tiles_y + tile_y
   *
   * @param {number} tileX - Tile X coordinate
   * @param {number} tileY - Tile Y coordinate
   * @returns {number} - Row group index
   */
  computeRowGroupIndex(tileX, tileY) {
    return tileX * this.numTilesY + tileY;
  }

  /**
   * For chunked mode: compute which file and local row group index
   * @param {number} globalRowGroupIndex - Global row group index
   * @returns {{fileIndex: number, localIndex: number}}
   */
  computeChunkLocation(globalRowGroupIndex) {
    const fileIndex = Math.floor(
      globalRowGroupIndex / this.maxRowGroupsPerFile
    );
    const localIndex = globalRowGroupIndex % this.maxRowGroupsPerFile;
    return { fileIndex, localIndex };
  }

  /**
   * Check if the server supports Range requests (needed for streaming)
   * @param {string} url - URL to check
   * @returns {Promise<boolean>}
   */
  async _checkRangeSupport(url) {
    try {
      const urlObj = new URL(url);
      if (urlObj.hostname === 'localhost' || urlObj.hostname === '127.0.0.1') {
        return true;
      }

      const response = await fetch(url, {
        method: 'GET',
        headers: { Range: 'bytes=0-7' },
      });

      if (!response.ok && response.status !== 206) {
        // console.log(
        //   `[RowGroupTileReader] Range check failed with status ${response.status}`
        // );
        return false;
      }

      const footerResponse = await fetch(url, {
        method: 'GET',
        headers: { Range: 'bytes=-8' },
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        // console.log(`[RowGroupTileReader] Footer range check failed`);
        return false;
      }

      return true;
    } catch {
      // Range check failed
      return false;
    }
  }

  /**
   * Get or create a ParquetFile for a specific chunk file
   * @param {number} fileIndex - Index of the chunk file
   * @returns {Promise<ParquetFile>}
   */
  async _getParquetFile(fileIndex) {
    // Note: We intentionally DON'T cache ParquetFile objects because
    // parquet-wasm's ParquetFile.read() is not safe for concurrent calls.
    // Each read gets a fresh ParquetFile instance.
    const fileName = this.files[fileIndex];
    if (!fileName) {
      throw new Error(
        `[RowGroupTileReader] No file for index ${fileIndex}. Available: ${this.files.length} files`
      );
    }

    const fileUrl = `${this.baseUrl}/${this.directory}/${fileName}`;
    const pq = await getPq();

    // console.log(`[RowGroupTileReader] Loading chunk file: ${fileName}`);
    const parquetFile = await pq.ParquetFile.fromUrl(fileUrl);

    return parquetFile;
  }

  /**
   * Initialize the reader (for single file mode or first access)
   */
  async initialize() {
    if (this.initialized) {
      return;
    }

    const pq = await getPq();

    if (!this.chunkedMode) {
      // Single file mode
      const rangeSupported = await this._checkRangeSupport(this.url);

      if (!rangeSupported) {
        throw new Error(
          `[RowGroupTileReader] Range requests not supported for ${this.url}. ` +
            `Row group mode requires a server that supports HTTP Range requests with CORS.`
        );
      }

      // console.log(
      //   `[RowGroupTileReader] Range requests supported, creating streaming ParquetFile...`
      // );
      this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
      // Metadata available via this.parquetFile.metadata() if needed
    } else {
      // Chunked mode - check range support on first file
      const firstFileUrl = `${this.baseUrl}/${this.directory}/${this.files[0]}`;
      const rangeSupported = await this._checkRangeSupport(firstFileUrl);

      if (!rangeSupported) {
        throw new Error(
          `[RowGroupTileReader] Range requests not supported. ` +
            `Row group mode requires a server that supports HTTP Range requests with CORS.`
        );
      }

      // console.log(
      //   `[RowGroupTileReader] Chunked mode enabled: ${this.files.length} files, ` +
      //     `${this.totalRowGroups} total row groups, max ${this.maxRowGroupsPerFile} per file`
      // );
    }

    this.initialized = true;
  }

  /**
   * Check if tile coordinates are within the grid bounds
   * @param {number} tileX - Tile X coordinate
   * @param {number} tileY - Tile Y coordinate
   * @returns {boolean} - True if within bounds
   */
  isValidTile(tileX, tileY) {
    return (
      tileX >= 0 &&
      tileX < this.numTilesX &&
      tileY >= 0 &&
      tileY < this.numTilesY
    );
  }

  /**
   * Read data for specific tiles using formula-based indexing
   * @param {Array<{tile_x: number, tile_y: number}>} tilesInView - Array of tile coordinates
   * @returns {Promise<arrow.Table|null>} - Arrow Table with data for requested tiles
   */
  async readTiles(tilesInView, options = {}) {
    if (!this.initialized) {
      await this.initialize();
    }

    // Compute row group indices using formula
    const rowGroupIndices = [];
    for (const tile of tilesInView) {
      if (this.isValidTile(tile.tile_x, tile.tile_y)) {
        const index = this.computeRowGroupIndex(tile.tile_x, tile.tile_y);
        rowGroupIndices.push(index);
      }
    }

    if (rowGroupIndices.length === 0) {
      // console.log(
      //   `[RowGroupTileReader] No valid tiles in request. Grid: ${this.numTilesX}x${this.numTilesY}`
      // );
      return null;
    }

    // Remove duplicates and sort
    const uniqueIndices = [...new Set(rowGroupIndices)].sort((a, b) => a - b);
    const returnTablesArray = options.returnTablesArray === true;
    const cacheKey = `${returnTablesArray ? 'tables' : 'table'}:${uniqueIndices.join(',')}`;
    const cachedRead = this._getCachedRead(cacheKey);
    if (cachedRead) {
      return cachedRead;
    }

    const readPromise = this._readRowGroups(uniqueIndices, options).catch(
      () => {
        this.requestCache.delete(cacheKey);
        return null;
      }
    );

    return this._setCachedRead(cacheKey, readPromise);
  }

  /**
   * Check if streaming mode is active
   * @returns {boolean}
   */
  isStreaming() {
    return this.initialized;
  }
}

/**
 * Factory function to create and initialize a RowGroupTileReader
 * @param {string} baseUrl - Base URL for landscape files
 * @param {Object} tileGrid - Grid dimensions
 * @param {Object|string} fileConfig - File configuration
 * @returns {Promise<RowGroupTileReader>} - Initialized reader
 */
export async function createRowGroupTileReader(baseUrl, tileGrid, fileConfig) {
  const reader = new RowGroupTileReader(baseUrl, tileGrid, fileConfig);
  await reader.initialize();
  return reader;
}

export default RowGroupTileReader;
