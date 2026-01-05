/**
 * ImageRowGroupReader - Reads image tiles from row-grouped parquet files
 *
 * Supports both:
 * - Single file mode (legacy): one parquet file with all row groups
 * - Chunked mode: multiple parquet files, each with max N row groups
 *
 * Each image tile is stored as a row group with binary image data.
 * Returns Blob URLs that can be used directly with deck.gl BitmapLayer.
 */

import * as arrow from 'apache-arrow';

import { getPq } from './pqInitializer';

/**
 * ImageRowGroupReader class for efficient image tile access via parquet
 */
export class ImageRowGroupReader {
  /**
   * Create a new ImageRowGroupReader
   * @param {string} baseUrl - Base URL for the dataset
   * @param {Object|string} imageConfig - Image configuration object or URL path
   * @param {Object} zoomInfo - Zoom level info from landscape_parameters (can be in imageConfig)
   */
  constructor(baseUrl, imageConfig, zoomInfo = null) {
    this.baseUrl = baseUrl;
    this.initialized = false;
    this.useStreaming = true;
    this.blobCache = new Map(); // Cache blob URLs to avoid recreation

    // Determine mode based on imageConfig type
    if (typeof imageConfig === 'string') {
      // Legacy: single file path
      this.chunkedMode = false;
      this.url = `${baseUrl}/${imageConfig}`;
      this.parquetFile = null;
      this.zoomInfo = zoomInfo || {};
    } else if (typeof imageConfig === 'object' && imageConfig.files) {
      // Chunked mode: directory with chunk files
      this.chunkedMode = true;
      this.directory = imageConfig.directory || 'pyramid_images';
      this.files = imageConfig.files;
      this.maxRowGroupsPerFile = imageConfig.max_row_groups_per_file || 2000;
      this.totalRowGroups = imageConfig.total_row_groups || 0;
      this.zoomInfo = imageConfig.zoom_info || zoomInfo || {};
      // eslint-disable-next-line no-console
      console.log(
        `[ImageRowGroupReader] Chunked mode: ${this.files.length} files, ` +
          `${this.totalRowGroups} total tiles`
      );
    } else if (typeof imageConfig === 'object' && imageConfig.path) {
      // Legacy: object with path property
      this.chunkedMode = false;
      this.url = `${baseUrl}/${imageConfig.path}`;
      this.parquetFile = null;
      this.zoomInfo = imageConfig.zoom_info || zoomInfo || {};
    } else {
      throw new Error(
        '[ImageRowGroupReader] Invalid imageConfig: must be string path or object with files/path'
      );
    }
  }

  /**
   * Check if the server supports Range requests (needed for streaming)
   * @param {string} testUrl - URL to test (optional, uses first file or main url)
   * @returns {Promise<boolean>}
   */
  async _checkRangeSupport(testUrl = null) {
    const url = testUrl || (this.chunkedMode ? this._getFileUrl(0) : this.url);

    try {
      // For localhost, trust that Range requests work (skip expensive checks)
      const urlObj = new URL(url);
      if (urlObj.hostname === 'localhost' || urlObj.hostname === '127.0.0.1') {
        return true;
      }

      // For remote servers, do a full Range request check
      const response = await fetch(url, {
        method: 'GET',
        headers: { Range: 'bytes=0-7' },
      });

      if (!response.ok && response.status !== 206) {
        // eslint-disable-next-line no-console
        console.log(
          `[ImageRowGroupReader] Range check failed with status ${response.status}`
        );
        return false;
      }

      const footerResponse = await fetch(url, {
        method: 'GET',
        headers: { Range: 'bytes=-8' },
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        // eslint-disable-next-line no-console
        console.log(
          `[ImageRowGroupReader] Footer range check failed with status ${footerResponse.status}`
        );
        return false;
      }

      const isPartial =
        response.status === 206 && footerResponse.status === 206;
      return isPartial || response.headers.get('Accept-Ranges') === 'bytes';
    } catch (error) {
      // eslint-disable-next-line no-console
      console.log(`[ImageRowGroupReader] Range check failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Get the URL for a chunk file by index
   * @param {number} fileIndex - Index of the chunk file
   * @returns {string} - Full URL to the chunk file
   */
  _getFileUrl(fileIndex) {
    if (!this.chunkedMode) {
      return this.url;
    }
    const fileName = this.files[fileIndex];
    return `${this.baseUrl}/${this.directory}/${fileName}`;
  }

  /**
   * Compute which file and local row group index for a global row group index
   * @param {number} globalIndex - Global row group index
   * @returns {{fileIndex: number, localIndex: number}}
   */
  _computeChunkLocation(globalIndex) {
    const fileIndex = Math.floor(globalIndex / this.maxRowGroupsPerFile);
    const localIndex = globalIndex % this.maxRowGroupsPerFile;
    return { fileIndex, localIndex };
  }

  /**
   * Get a ParquetFile for the specified chunk file
   * @param {number} fileIndex - Index of the chunk file
   * @returns {Promise<Object>} - ParquetFile instance
   */
  async _getParquetFile(fileIndex) {
    const fileUrl = this._getFileUrl(fileIndex);
    const pq = await getPq();
    return pq.ParquetFile.fromUrl(fileUrl);
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

    // Require Range request support - no full file fallback for row groups
    const rangeSupported = await this._checkRangeSupport();

    if (!rangeSupported) {
      const testUrl = this.chunkedMode ? this._getFileUrl(0) : this.url;
      throw new Error(
        `[ImageRowGroupReader] Range requests not supported for ${testUrl}. ` +
          `Row group mode requires a server that supports HTTP Range requests with CORS.`
      );
    }

    if (!pq.ParquetFile || typeof pq.ParquetFile.fromUrl !== 'function') {
      throw new Error(
        `[ImageRowGroupReader] ParquetFile.fromUrl not available. ` +
          `Please ensure parquet-wasm is properly initialized.`
      );
    }

    if (this.chunkedMode) {
      // Chunked mode: files are loaded lazily
      // eslint-disable-next-line no-console
      console.log(
        `[ImageRowGroupReader] Chunked mode enabled: ${this.files.length} files, ` +
          `${this.totalRowGroups} total tiles`
      );
    } else {
      // Single file mode: load the parquet file
      // eslint-disable-next-line no-console
      console.log(
        `[ImageRowGroupReader] Range requests supported, creating streaming ParquetFile...`
      );
      this.parquetFile = await pq.ParquetFile.fromUrl(this.url);

      const metadata = this.parquetFile.metadata();
      const numRowGroups = metadata.numRowGroups();
      // eslint-disable-next-line no-console
      console.log(
        `[ImageRowGroupReader] Streaming mode enabled, ${numRowGroups} tiles available`
      );
    }

    // eslint-disable-next-line no-console
    console.log(
      `[ImageRowGroupReader] zoomInfo available: ${this.zoomInfo ? Object.keys(this.zoomInfo).join(', ') : 'none'}`
    );
    this.initialized = true;
  }

  /**
   * Compute the row group index for an image tile
   *
   * The formula accounts for zoom levels:
   * - Each zoom level has tiles stored contiguously
   * - row_group_index = zoom_offset + tile_x * num_tiles_y + tile_y
   *
   * @param {number} zoom - Zoom level
   * @param {number} tileX - Tile X coordinate
   * @param {number} tileY - Tile Y coordinate
   * @returns {number|null} - Row group index or null if not found
   */
  computeRowGroupIndex(zoom, tileX, tileY) {
    // JSON keys are strings, so convert zoom to string
    const zoomKey = String(zoom);
    const zoomData = this.zoomInfo[zoomKey];

    if (!zoomData) {
      console.log(
        `[ImageRowGroupReader] No zoom data for level ${zoom}, available: ${Object.keys(this.zoomInfo).join(', ')}`
      );
      return null;
    }

    const { row_group_offset, num_tiles_x, num_tiles_y } = zoomData;

    // Check bounds
    if (
      tileX < 0 ||
      tileX >= num_tiles_x ||
      tileY < 0 ||
      tileY >= num_tiles_y
    ) {
      return null;
    }

    // Column-major ordering within each zoom level
    return row_group_offset + tileX * num_tiles_y + tileY;
  }

  /**
   * Read an image tile and return as a Blob URL
   * @param {number} zoom - Zoom level
   * @param {number} tileX - Tile X coordinate
   * @param {number} tileY - Tile Y coordinate
   * @param {string} mimeType - Image MIME type (default: "image/webp")
   * @returns {Promise<string|null>} - Blob URL or null if tile not found
   */
  async readTile(zoom, tileX, tileY, mimeType = 'image/webp') {
    if (!this.initialized) {
      await this.initialize();
    }

    // Check cache first
    const cacheKey = `${zoom}_${tileX}_${tileY}`;
    if (this.blobCache.has(cacheKey)) {
      return this.blobCache.get(cacheKey);
    }

    const rowGroupIndex = this.computeRowGroupIndex(zoom, tileX, tileY);
    if (rowGroupIndex === null) {
      return null;
    }

    try {
      let wasmTable;

      if (this.chunkedMode) {
        // Chunked mode: find the right file and read from it
        const { fileIndex, localIndex } = this._computeChunkLocation(rowGroupIndex);

        if (fileIndex >= this.files.length) {
          // eslint-disable-next-line no-console
          console.warn(
            `[ImageRowGroupReader] File index ${fileIndex} out of range (${this.files.length} files)`
          );
          return null;
        }

        const pqFile = await this._getParquetFile(fileIndex);
        wasmTable = await pqFile.read({ rowGroups: [localIndex] });
      } else {
        // Single file mode
        wasmTable = await this.parquetFile.read({
          rowGroups: [rowGroupIndex],
        });
      }

      const arrowIPC = wasmTable.intoIPCStream();
      const table = arrow.tableFromIPC(arrowIPC);

      // Get the image data column
      const imageDataCol = table.getChild('image_data');
      if (!imageDataCol || imageDataCol.length === 0) {
        return null;
      }

      const imageBytes = imageDataCol.get(0);
      if (!imageBytes || imageBytes.length === 0) {
        return null;
      }

      // Create Blob and URL
      const blob = new Blob([imageBytes], { type: mimeType });
      const blobUrl = URL.createObjectURL(blob);

      // Cache it
      this.blobCache.set(cacheKey, blobUrl);

      return blobUrl;
    } catch (error) {
      // eslint-disable-next-line no-console
      console.warn(
        `[ImageRowGroupReader] Error reading tile z${zoom} ${tileX}_${tileY}:`,
        error
      );
      return null;
    }
  }

  /**
   * Clear the blob URL cache and revoke all URLs
   */
  clearCache() {
    for (const blobUrl of this.blobCache.values()) {
      URL.revokeObjectURL(blobUrl);
    }
    this.blobCache.clear();
  }

  /**
   * Get cache size
   * @returns {number}
   */
  getCacheSize() {
    return this.blobCache.size;
  }

  /**
   * Check if streaming mode is active
   * @returns {boolean}
   */
  isStreaming() {
    return this.useStreaming && this.parquetFile !== null;
  }
}

/**
 * Create a getTileData function compatible with deck.gl TileLayer
 * @param {ImageRowGroupReader} reader - Initialized image reader
 * @param {number} maxPyramidZoom - Maximum zoom level of the pyramid
 * @returns {Function} - getTileData function for TileLayer
 */
export function createGetTileDataFromParquet(reader, maxPyramidZoom) {
  return async ({ index }) => {
    const { x, y, z } = index;
    // deck.gl uses negative z values, convert to actual zoom level
    const actualZoom = maxPyramidZoom + z;

    const blobUrl = await reader.readTile(actualZoom, x, y);

    if (!blobUrl) {
      return null;
    }

    // Load the image from the blob URL
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = blobUrl;
    });
  };
}

/**
 * Factory function to create and initialize an ImageRowGroupReader
 * @param {string} baseUrl - Base URL for the dataset
 * @param {Object|string} imageConfig - Image configuration object or path
 * @param {Object} zoomInfo - Zoom level info (optional, can be in imageConfig)
 * @returns {Promise<ImageRowGroupReader>} - Initialized reader
 */
export async function createImageRowGroupReader(baseUrl, imageConfig, zoomInfo = null) {
  const reader = new ImageRowGroupReader(baseUrl, imageConfig, zoomInfo);
  await reader.initialize();
  return reader;
}

export default ImageRowGroupReader;
