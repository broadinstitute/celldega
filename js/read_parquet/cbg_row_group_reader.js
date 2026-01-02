/**
 * CBGRowGroupReader - Reads gene expression data from a row-grouped parquet file
 *
 * Each gene is stored as a separate row group, enabling efficient access to
 * individual gene expression data without loading the entire file.
 */

import * as arrow from "apache-arrow";

import { getPq } from "./pqInitializer";

/**
 * CBGRowGroupReader class for efficient gene-based expression data access
 */
export class CBGRowGroupReader {
  /**
   * Create a new CBGRowGroupReader
   * @param {string} parquetUrl - URL to the cbg.parquet file
   */
  constructor(parquetUrl) {
    this.url = parquetUrl;
    this.initialized = false;
    this.parquetFile = null;
    this.geneToRowGroup = {}; // Will be loaded from parquet metadata
    this.useStreaming = true;
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
        console.log(`[CBGRowGroupReader] Range check failed with status ${response.status}`);
        return false;
      }

      const footerResponse = await fetch(this.url, {
        method: "GET",
        headers: { Range: "bytes=-8" },
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        console.log(`[CBGRowGroupReader] Footer range check failed with status ${footerResponse.status}`);
        return false;
      }

      const isPartial = response.status === 206 && footerResponse.status === 206;
      return isPartial || response.headers.get("Accept-Ranges") === "bytes";
    } catch (error) {
      console.log(`[CBGRowGroupReader] Range check failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Initialize the reader by loading parquet metadata
   * @returns {Promise<void>}
   */
  async initialize() {
    if (this.initialized) {
      return;
    }

    const pq = await getPq();

    // console.log(`[CBGRowGroupReader] Initializing from: ${this.url}`);

    // Require Range request support - no full file fallback for row groups
    const rangeSupported = await this._checkRangeSupport();

    if (!rangeSupported) {
      throw new Error(
        `[CBGRowGroupReader] Range requests not supported for ${this.url}. ` +
        `Row group mode requires a server that supports HTTP Range requests with CORS.`
      );
    }

    if (!pq.ParquetFile || typeof pq.ParquetFile.fromUrl !== "function") {
      throw new Error(
        `[CBGRowGroupReader] ParquetFile.fromUrl not available. ` +
        `Please ensure parquet-wasm is properly initialized.`
      );
    }

    // Use ParquetFile for streaming access
    console.log(`[CBGRowGroupReader] Range requests supported, creating streaming ParquetFile...`);
    this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
    this.useStreaming = true;

    // Get metadata to build gene index
    const metadata = this.parquetFile.metadata();
    const numRowGroups = metadata.numRowGroups;
    console.log(
      `[CBGRowGroupReader] Streaming mode enabled, ${numRowGroups} row groups available`
    );

    // Try to get gene_to_row_group from parquet key-value metadata
    // Read one row group to access schema metadata
    const sampleTable = await this.parquetFile.read({ rowGroups: [0] });
    const arrowIPC = sampleTable.intoIPCStream();
    const arrowTable = arrow.tableFromIPC(arrowIPC);

    const schemaMetadata = arrowTable.schema.metadata;
    if (schemaMetadata && schemaMetadata.has("gene_to_row_group")) {
      try {
        this.geneToRowGroup = JSON.parse(schemaMetadata.get("gene_to_row_group"));
        console.log(
          `[CBGRowGroupReader] Loaded gene index from metadata: ${Object.keys(this.geneToRowGroup).length} genes`
        );
      } catch (e) {
        console.warn(`[CBGRowGroupReader] Failed to parse gene_to_row_group:`, e);
        // Fall back to building index manually
        this.geneToRowGroup = await this._buildGeneIndex(numRowGroups);
      }
    } else {
      console.log(`[CBGRowGroupReader] No gene_to_row_group in metadata, building index...`);
      this.geneToRowGroup = await this._buildGeneIndex(numRowGroups);
    }

    this.initialized = true;
  }

  /**
   * Build gene index by reading each row group's gene column
   * @param {number} numRowGroups - Number of row groups in the file
   * @returns {Promise<Object>} - Map from gene name to row group index
   */
  async _buildGeneIndex(numRowGroups) {
    const index = {};

    // Read a sample of row groups to build the index
    // Each row group should have a consistent gene value
    for (let i = 0; i < numRowGroups; i++) {
      try {
        const table = await this.parquetFile.read({ rowGroups: [i] });
        const arrowIPC = table.intoIPCStream();
        const arrowTable = arrow.tableFromIPC(arrowIPC);

        const geneCol = arrowTable.getChild("gene");
        if (geneCol && geneCol.length > 0) {
          const geneName = geneCol.get(0);
          index[geneName] = i;
        }
      } catch (error) {
        console.warn(`[CBGRowGroupReader] Error reading row group ${i}:`, error);
      }
    }

    console.log(`[CBGRowGroupReader] Built index for ${Object.keys(index).length} genes`);
    return index;
  }

  /**
   * Build gene index from a full Arrow table
   * @param {arrow.Table} table - Full Arrow table
   * @returns {Object} - Map from gene name to row group index
   */
  _buildGeneIndexFromTable(table) {
    const index = {};
    let currentRowGroup = 0;

    // Each batch corresponds to a row group
    for (const batch of table.batches) {
      const geneCol = batch.getChild("gene");
      if (geneCol && geneCol.length > 0) {
        const geneName = geneCol.get(0);
        index[geneName] = currentRowGroup;
      }
      currentRowGroup++;
    }

    return index;
  }

  /**
   * Check if a gene exists in the dataset
   * @param {string} geneName - Gene name
   * @returns {boolean}
   */
  hasGene(geneName) {
    return geneName in this.geneToRowGroup;
  }

  /**
   * Get the row group index for a gene
   * @param {string} geneName - Gene name
   * @returns {number|null} - Row group index or null if not found
   */
  getGeneRowGroupIndex(geneName) {
    return this.geneToRowGroup[geneName] ?? null;
  }

  /**
   * Read expression data for a specific gene
   * @param {string} geneName - Gene name
   * @returns {Promise<arrow.Table|null>} - Arrow table with cell_id, expression columns
   */
  async readGene(geneName) {
    if (!this.initialized) {
      await this.initialize();
    }

    const rowGroupIndex = this.getGeneRowGroupIndex(geneName);
    if (rowGroupIndex === null) {
      console.log(`[CBGRowGroupReader] Gene not found: ${geneName}`);
      return null;
    }

    console.log(`[CBGRowGroupReader] Reading gene ${geneName} (row group ${rowGroupIndex})`);

    // Use streaming mode with HTTP Range Requests
    const wasmTable = await this.parquetFile.read({ rowGroups: [rowGroupIndex] });
    const arrowIPC = wasmTable.intoIPCStream();
    const table = arrow.tableFromIPC(arrowIPC);

    console.log(`[CBGRowGroupReader] Read ${table.numRows} cells for gene ${geneName}`);

    return table;
  }

  /**
   * Get the number of genes in the dataset
   * @returns {number}
   */
  getNumGenes() {
    return Object.keys(this.geneToRowGroup).length;
  }

  /**
   * Get all gene names
   * @returns {string[]}
   */
  getGeneNames() {
    return Object.keys(this.geneToRowGroup);
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
 * Factory function to create and initialize a CBGRowGroupReader
 * @param {string} parquetUrl - URL to the cbg.parquet file
 * @returns {Promise<CBGRowGroupReader>} - Initialized reader
 */
export async function createCBGRowGroupReader(parquetUrl) {
  const reader = new CBGRowGroupReader(parquetUrl);
  await reader.initialize();
  return reader;
}

export default CBGRowGroupReader;
