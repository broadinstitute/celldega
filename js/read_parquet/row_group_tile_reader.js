/**
 * RowGroupTileReader - Efficient tile-based data access from row-grouped parquet files
 *
 * Uses HTTP Range Requests to fetch only the needed row groups, providing
 * performance comparable to individual tile files.
 *
 * Row group indices are computed using a simple formula:
 *   row_group_index = tile_x * num_tiles_y + tile_y
 *
 * This requires only the grid dimensions (num_tiles_x, num_tiles_y) - no mapping needed.
 */

import * as arrow from 'apache-arrow';

import { getPq } from './pqInitializer';

/**
 * RowGroupTileReader class for efficient streaming tile-based data access
 */
export class RowGroupTileReader {
  /**
   * Create a new RowGroupTileReader
   * @param {string} parquetUrl - URL to the row-grouped parquet file
   * @param {Object} tileGrid - Grid dimensions { num_tiles_x, num_tiles_y }
   */
  constructor(parquetUrl, tileGrid = null) {
    this.url = parquetUrl;
    this.numTilesX = tileGrid?.num_tiles_x || 0;
    this.numTilesY = tileGrid?.num_tiles_y || 0;
    this.initialized = false;
    this.parquetFile = null;
    this.useStreaming = true;
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
   * Check if the server supports Range requests (needed for streaming)
   * @returns {Promise<boolean>}
   */
  async _checkRangeSupport() {
    try {
      // For localhost, trust that Range requests work (skip expensive checks)
      const urlObj = new URL(this.url);
      if (urlObj.hostname === 'localhost' || urlObj.hostname === '127.0.0.1') {
        return true;
      }

      // For remote servers, do a full Range request check to catch CDN issues
      const response = await fetch(this.url, {
        method: 'GET',
        headers: {
          Range: 'bytes=0-7',
        },
      });

      if (!response.ok && response.status !== 206) {
        console.log(
          `[RowGroupTileReader] Range check failed with status ${response.status}`
        );
        return false;
      }

      // Also test suffix range (what parquet-wasm uses for footer)
      const footerResponse = await fetch(this.url, {
        method: 'GET',
        headers: {
          Range: 'bytes=-8',
        },
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        console.log(
          `[RowGroupTileReader] Footer range check failed with status ${footerResponse.status}`
        );
        return false;
      }

      const isPartial =
        response.status === 206 && footerResponse.status === 206;
      const acceptRanges = response.headers.get('Accept-Ranges');

      return isPartial || acceptRanges === 'bytes';
    } catch (error) {
      console.log(`[RowGroupTileReader] Range check failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Initialize the reader
   * @returns {Promise<void>}
   */
  async initialize() {
    if (this.initialized) {
      return;
    }

    const pq = await getPq();

    // console.log(`[RowGroupTileReader] Initializing from: ${this.url}`);

    // First check if Range requests are supported (also validates CORS)
    const rangeSupported = await this._checkRangeSupport();

    // Require Range request support - no full file fallback for row groups
    if (!rangeSupported) {
      throw new Error(
        `[RowGroupTileReader] Range requests not supported for ${this.url}. ` +
          `Row group mode requires a server that supports HTTP Range requests with CORS.`
      );
    }

    if (!pq.ParquetFile || typeof pq.ParquetFile.fromUrl !== 'function') {
      throw new Error(
        `[RowGroupTileReader] ParquetFile.fromUrl not available. ` +
          `Please ensure parquet-wasm is properly initialized.`
      );
    }

    // Use ParquetFile for streaming access with range requests
    console.log(
      `[RowGroupTileReader] Range requests supported, creating streaming ParquetFile...`
    );
    this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
    this.useStreaming = true;

    // Get metadata for verification
    const metadata = this.parquetFile.metadata();
    const expectedRowGroups = this.numTilesX * this.numTilesY;
    console.log(
      `[RowGroupTileReader] Streaming mode enabled, ${metadata.numRowGroups} row groups (expected ${expectedRowGroups})`
    );

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
        `[RowGroupTileReader] No valid tiles in request. Grid: ${this.numTilesX}x${this.numTilesY}, requested:`,
        tilesInView.slice(0, 5)
      );
      return null;
    }

    // Remove duplicates and sort
    const uniqueIndices = [...new Set(rowGroupIndices)].sort((a, b) => a - b);

    // Verbose logging disabled
    // console.log(`[RowGroupTileReader] Reading ${uniqueIndices.length} row groups`);

    // Use streaming mode with HTTP Range Requests
    const wasmTable = await this.parquetFile.read({
      rowGroups: uniqueIndices,
    });

    // Convert to Arrow Table
    const arrowIPC = wasmTable.intoIPCStream();
    const table = arrow.tableFromIPC(arrowIPC);

    // console.log(`[RowGroupTileReader] Read ${table.numRows} rows`);

    return table;
  }

  /**
   * Read data for a single tile
   * @param {number} tileX - Tile X coordinate
   * @param {number} tileY - Tile Y coordinate
   * @returns {Promise<arrow.Table|null>} - Arrow Table with tile data
   */
  async readTile(tileX, tileY) {
    return this.readTiles([{ tile_x: tileX, tile_y: tileY }]);
  }

  /**
   * Get the total number of tiles in the grid
   * @returns {number}
   */
  getNumTiles() {
    return this.numTilesX * this.numTilesY;
  }

  /**
   * Get grid dimensions
   * @returns {{num_tiles_x: number, num_tiles_y: number}}
   */
  getGridDimensions() {
    return {
      num_tiles_x: this.numTilesX,
      num_tiles_y: this.numTilesY,
    };
  }

  /**
   * Check if streaming mode is active (uses HTTP Range Requests)
   * @returns {boolean}
   */
  isStreaming() {
    return this.useStreaming && this.parquetFile !== null;
  }
}

/**
 * Factory function to create and initialize a RowGroupTileReader
 * @param {string} parquetUrl - URL to the row-grouped parquet file
 * @param {Object} tileGrid - Grid dimensions { num_tiles_x, num_tiles_y }
 * @returns {Promise<RowGroupTileReader>} - Initialized reader
 */
export async function createRowGroupTileReader(parquetUrl, tileGrid = null) {
  const reader = new RowGroupTileReader(parquetUrl, tileGrid);
  await reader.initialize();
  return reader;
}

export default RowGroupTileReader;
