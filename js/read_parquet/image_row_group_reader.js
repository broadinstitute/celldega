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
      const response = await fetch(this.url, { method: "HEAD" });
      if (!response.ok) return false;
      return response.headers.get("Accept-Ranges") === "bytes";
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

    // First check if Range requests are supported (also validates CORS)
    const rangeSupported = await this._checkRangeSupport();

    // Try to use ParquetFile for streaming access
    if (rangeSupported && pq.ParquetFile && typeof pq.ParquetFile.fromUrl === "function") {
      try {
        console.log(`[ImageRowGroupReader] Range requests supported, creating streaming ParquetFile...`);
        this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
        this.useStreaming = true;

        const metadata = this.parquetFile.metadata();
        console.log(
          `[ImageRowGroupReader] Streaming mode enabled, ${metadata.numRowGroups} tiles available`
        );
      } catch (error) {
        console.warn(
          `[ImageRowGroupReader] Streaming failed, falling back:`,
          error.message
        );
        this.useStreaming = false;
      }
    } else {
      if (!rangeSupported) {
        console.log(`[ImageRowGroupReader] Range requests not supported, using full fetch mode`);
      }
      this.useStreaming = false;
    }

    // Fallback: fetch entire file
    if (!this.useStreaming) {
      console.log(`[ImageRowGroupReader] Fetching full file...`);
      const response = await fetch(this.url);
      if (!response.ok) {
        throw new Error(`Failed to fetch image parquet: ${response.statusText}`);
      }
      const arrayBuffer = await response.arrayBuffer();
      this.parquetData = new Uint8Array(arrayBuffer);
      console.log(
        `[ImageRowGroupReader] Loaded ${(this.parquetData.length / 1024 / 1024).toFixed(2)} MB`
      );

      // If zoomInfo wasn't provided, try to read it from parquet metadata
      if (!this.zoomInfo || Object.keys(this.zoomInfo).length === 0) {
        try {
          const wasmTable = pq.readParquet(this.parquetData);
          const arrowIPC = wasmTable.intoIPCStream();
          const table = arrow.tableFromIPC(arrowIPC);

          // Arrow schema metadata is a Map
          const metadata = table.schema.metadata;
          if (metadata) {
            const zoomInfoStr = metadata.get("zoom_info");
            if (zoomInfoStr) {
              this.zoomInfo = JSON.parse(zoomInfoStr);
              console.log(`[ImageRowGroupReader] Read zoom_info from parquet metadata: ${Object.keys(this.zoomInfo).length} zoom levels`);
            }
          }
        } catch (e) {
          console.warn(`[ImageRowGroupReader] Could not read zoom_info from metadata: ${e.message}`);
        }
      }
    }

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
      let wasmTable;
      const pq = await getPq();

      if (this.useStreaming && this.parquetFile) {
        wasmTable = await this.parquetFile.read({ rowGroups: [rowGroupIndex] });
      } else {
        wasmTable = pq.readParquet(this.parquetData, { rowGroups: [rowGroupIndex] });
      }

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
