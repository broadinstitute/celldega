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

import {getPq} from './pqInitializer';

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
    this.baseUrl = baseUrl;
    this.numTilesX = tileGrid?.num_tiles_x || 0;
    this.numTilesY = tileGrid?.num_tiles_y || 0;
    this.initialized = false;

    // Determine mode: chunked or single file
    if (typeof fileConfig === 'string') {
      // Legacy single file mode
      this.chunkedMode = false;
      this.url = `${baseUrl}/${fileConfig}`;
      this.parquetFile = null;
    } else if (typeof fileConfig === 'object' && fileConfig.files) {
      // Chunked mode
      this.chunkedMode = true;
      this.directory = fileConfig.directory;
      this.files = fileConfig.files;
      this.maxRowGroupsPerFile = fileConfig.max_row_groups_per_file || 10000;
      this.totalRowGroups = fileConfig.total_row_groups || 0;
      this.parquetFiles = {}; // Lazy-loaded map of file_index -> ParquetFile
    } else {
      throw new Error(
        '[RowGroupTileReader] Invalid fileConfig: must be string URL or chunk config object'
      );
    }
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
    const fileIndex = Math.floor(globalRowGroupIndex / this.maxRowGroupsPerFile);
    const localIndex = globalRowGroupIndex % this.maxRowGroupsPerFile;
    return {fileIndex, localIndex};
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
        headers: {Range: 'bytes=0-7'},
      });

      if (!response.ok && response.status !== 206) {
        console.log(
          `[RowGroupTileReader] Range check failed with status ${response.status}`
        );
        return false;
      }

      const footerResponse = await fetch(url, {
        method: 'GET',
        headers: {Range: 'bytes=-8'},
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        console.log(`[RowGroupTileReader] Footer range check failed`);
        return false;
      }

      return true;
    } catch (error) {
      console.log(`[RowGroupTileReader] Range check failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Get or create a ParquetFile for a specific chunk file
   * @param {number} fileIndex - Index of the chunk file
   * @returns {Promise<ParquetFile>}
   */
  async _getParquetFile(fileIndex) {
    if (this.parquetFiles[fileIndex]) {
      return this.parquetFiles[fileIndex];
    }

    const fileName = this.files[fileIndex];
    if (!fileName) {
      throw new Error(
        `[RowGroupTileReader] No file for index ${fileIndex}. Available: ${this.files.length} files`
      );
    }

    const fileUrl = `${this.baseUrl}/${this.directory}/${fileName}`;
    const pq = await getPq();

    console.log(`[RowGroupTileReader] Loading chunk file: ${fileName}`);
    const parquetFile = await pq.ParquetFile.fromUrl(fileUrl);
    this.parquetFiles[fileIndex] = parquetFile;

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

      console.log(
        `[RowGroupTileReader] Range requests supported, creating streaming ParquetFile...`
      );
      this.parquetFile = await pq.ParquetFile.fromUrl(this.url);

      const metadata = this.parquetFile.metadata();
      const expectedRowGroups = this.numTilesX * this.numTilesY;
      const actualRowGroups = metadata.numRowGroups();
      console.log(
        `[RowGroupTileReader] Streaming mode enabled, ${actualRowGroups} row groups (expected ${expectedRowGroups})`
      );
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

      console.log(
        `[RowGroupTileReader] Chunked mode enabled: ${this.files.length} files, ` +
          `${this.totalRowGroups} total row groups, max ${this.maxRowGroupsPerFile} per file`
      );
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
  async readTiles(tilesInView) {
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
      console.log(
        `[RowGroupTileReader] No valid tiles in request. Grid: ${this.numTilesX}x${this.numTilesY}`
      );
      return null;
    }

    // Remove duplicates and sort
    const uniqueIndices = [...new Set(rowGroupIndices)].sort((a, b) => a - b);

    try {
      if (!this.chunkedMode) {
        // Single file mode - read all from one file
        console.log(
          `[RowGroupTileReader] Reading ${uniqueIndices.length} row groups: ${uniqueIndices.slice(0, 5).join(', ')}${uniqueIndices.length > 5 ? '...' : ''}`
        );

        const wasmTable = await this.parquetFile.read({
          rowGroups: uniqueIndices,
        });
        const arrowIPC = wasmTable.intoIPCStream();
        const table = arrow.tableFromIPC(arrowIPC);

        console.log(`[RowGroupTileReader] Read ${table.numRows} rows`);
        return table;
      } else {
        // Chunked mode - partition by file and read from each
        const byFile = new Map();
        for (const globalIndex of uniqueIndices) {
          const {fileIndex, localIndex} = this.computeChunkLocation(globalIndex);
          if (!byFile.has(fileIndex)) {
            byFile.set(fileIndex, []);
          }
          byFile.get(fileIndex).push(localIndex);
        }

        console.log(
          `[RowGroupTileReader] Reading ${uniqueIndices.length} row groups from ${byFile.size} files`
        );

        // Read from each file and collect tables
        const tables = [];
        for (const [fileIndex, localIndices] of byFile) {
          console.log(
            `[RowGroupTileReader] File ${fileIndex}: reading local indices ${localIndices.slice(0, 10).join(', ')}${localIndices.length > 10 ? '...' : ''}`
          );
          const pqFile = await this._getParquetFile(fileIndex);
          const metadata = pqFile.metadata();
          console.log(
            `[RowGroupTileReader] File ${fileIndex} has ${metadata.numRowGroups()} row groups`
          );
          const wasmTable = await pqFile.read({rowGroups: localIndices});
          const arrowIPC = wasmTable.intoIPCStream();
          const table = arrow.tableFromIPC(arrowIPC);
          tables.push(table);
        }

        // Concatenate all tables
        if (tables.length === 0) {
          return null;
        } else if (tables.length === 1) {
          console.log(`[RowGroupTileReader] Read ${tables[0].numRows} rows`);
          return tables[0];
        } else {
          // Concatenate multiple tables using Arrow's concat
          const combined = arrow.tableConcat(tables);
          console.log(`[RowGroupTileReader] Read ${combined.numRows} rows from ${tables.length} files`);
          return combined;
        }
      }
    } catch (error) {
      console.error(`[RowGroupTileReader] Error reading row groups:`, error);
      return null;
    }
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
