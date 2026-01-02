/**
 * ImageRowGroupReader - Reads image tiles from a row-grouped parquet file
 *
 * Each image tile is stored as a row group with binary image data.
 * Returns Blob URLs that can be used directly with deck.gl BitmapLayer.
 */

import * as arrow from "apache-arrow";

import { getPq } from "./pqInitializer";

/**
 * ImageRowGroupReader class for efficient image tile access via parquet
 */
export class ImageRowGroupReader {
  /**
   * Create a new ImageRowGroupReader
   * @param {string} parquetUrl - URL to the image parquet file
   * @param {Object} zoomInfo - Zoom level info from landscape_parameters
   */
  constructor(parquetUrl, zoomInfo = null) {
    this.url = parquetUrl;
    this.zoomInfo = zoomInfo || {};
    this.initialized = false;
    this.parquetFile = null;
    this.useStreaming = true;
    this.blobCache = new Map(); // Cache blob URLs to avoid recreation
  }

  /**
   * Check if the server supports Range requests (needed for streaming)
   * @returns {Promise<boolean>}
   */
  async _checkRangeSupport() {
    try {
      // For localhost, trust that Range requests work (skip expensive checks)
      const urlObj = new URL(this.url);
      if (urlObj.hostname === "localhost" || urlObj.hostname === "127.0.0.1") {
        return true;
      }

      // For remote servers, do a full Range request check
      const response = await fetch(this.url, {
        method: "GET",
        headers: { Range: "bytes=0-7" },
      });

      if (!response.ok && response.status !== 206) {
        console.log(`[ImageRowGroupReader] Range check failed with status ${response.status}`);
        return false;
      }

      const footerResponse = await fetch(this.url, {
        method: "GET",
        headers: { Range: "bytes=-8" },
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        console.log(`[ImageRowGroupReader] Footer range check failed with status ${footerResponse.status}`);
        return false;
      }

      const isPartial = response.status === 206 && footerResponse.status === 206;
      return isPartial || response.headers.get("Accept-Ranges") === "bytes";
    } catch (error) {
      console.log(`[ImageRowGroupReader] Range check failed: ${error.message}`);
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

    // console.log(`[ImageRowGroupReader] Initializing from: ${this.url}`);

    // Require Range request support - no full file fallback for row groups
    const rangeSupported = await this._checkRangeSupport();

    if (!rangeSupported) {
      throw new Error(
        `[ImageRowGroupReader] Range requests not supported for ${this.url}. ` +
        `Row group mode requires a server that supports HTTP Range requests with CORS.`
      );
    }

    if (!pq.ParquetFile || typeof pq.ParquetFile.fromUrl !== "function") {
      throw new Error(
        `[ImageRowGroupReader] ParquetFile.fromUrl not available. ` +
        `Please ensure parquet-wasm is properly initialized.`
      );
    }

    // Use ParquetFile for streaming access
    console.log(`[ImageRowGroupReader] Range requests supported, creating streaming ParquetFile...`);
    this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
    this.useStreaming = true;

    const metadata = this.parquetFile.metadata();
    console.log(
      `[ImageRowGroupReader] Streaming mode enabled, ${metadata.numRowGroups} tiles available`
    );

    console.log(`[ImageRowGroupReader] zoomInfo available: ${this.zoomInfo ? Object.keys(this.zoomInfo).join(', ') : 'none'}`);
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
      console.log(`[ImageRowGroupReader] No zoom data for level ${zoom}, available: ${Object.keys(this.zoomInfo).join(', ')}`);
      return null;
    }

    const { row_group_offset, num_tiles_x, num_tiles_y } = zoomData;

    // Check bounds
    if (tileX < 0 || tileX >= num_tiles_x || tileY < 0 || tileY >= num_tiles_y) {
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
  async readTile(zoom, tileX, tileY, mimeType = "image/webp") {
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
      // Use streaming mode with HTTP Range Requests
      const wasmTable = await this.parquetFile.read({ rowGroups: [rowGroupIndex] });
      const arrowIPC = wasmTable.intoIPCStream();
      const table = arrow.tableFromIPC(arrowIPC);

      // Get the image data column
      const imageDataCol = table.getChild("image_data");
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
      console.warn(`[ImageRowGroupReader] Error reading tile z${zoom} ${tileX}_${tileY}:`, error);
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
 * @param {string} parquetUrl - URL to the image parquet file
 * @param {Object} zoomInfo - Zoom level info
 * @returns {Promise<ImageRowGroupReader>} - Initialized reader
 */
export async function createImageRowGroupReader(parquetUrl, zoomInfo = null) {
  const reader = new ImageRowGroupReader(parquetUrl, zoomInfo);
  await reader.initialize();
  return reader;
}

export default ImageRowGroupReader;
