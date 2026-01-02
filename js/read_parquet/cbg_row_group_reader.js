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
      const response = await fetch(this.url, { method: "HEAD" });
      if (!response.ok) return false;
      return response.headers.get("Accept-Ranges") === "bytes";
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

    // First check if Range requests are supported (also validates CORS)
    const rangeSupported = await this._checkRangeSupport();

    // Try to use ParquetFile for streaming access
    if (rangeSupported && pq.ParquetFile && typeof pq.ParquetFile.fromUrl === "function") {
      try {
        console.log(`[CBGRowGroupReader] Range requests supported, creating streaming ParquetFile...`);
        this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
        this.useStreaming = true;

        // Get metadata to build gene index
        const metadata = this.parquetFile.metadata();
        console.log(
          `[CBGRowGroupReader] Streaming mode enabled, ${metadata.numRowGroups} genes available`
        );

        // Try to get gene_to_row_group from parquet key-value metadata
        // For now, we'll need to build it by reading first row of each row group
        // This is a one-time cost on initialization
        this.geneToRowGroup = await this._buildGeneIndex(metadata.numRowGroups);
      } catch (error) {
        console.warn(
          `[CBGRowGroupReader] Streaming failed, falling back to full fetch:`,
          error.message
        );
        this.useStreaming = false;
      }
    } else {
      if (!rangeSupported) {
        console.log(`[CBGRowGroupReader] Range requests not supported, using full fetch mode`);
      }
      this.useStreaming = false;
    }

    // Fallback: fetch entire file
    if (!this.useStreaming) {
      console.log(`[CBGRowGroupReader] Fetching full file...`);
      const response = await fetch(this.url);
      if (!response.ok) {
        throw new Error(`Failed to fetch cbg parquet: ${response.statusText}`);
      }
      const arrayBuffer = await response.arrayBuffer();
      this.parquetData = new Uint8Array(arrayBuffer);

      // Build gene index from full file
      const wasmTable = pq.readParquet(this.parquetData);
      const arrowIPC = wasmTable.intoIPCStream();
      const table = arrow.tableFromIPC(arrowIPC);

      this.geneToRowGroup = this._buildGeneIndexFromTable(table);

      console.log(
        `[CBGRowGroupReader] Loaded ${(this.parquetData.length / 1024 / 1024).toFixed(2)} MB, ${Object.keys(this.geneToRowGroup).length} genes`
      );
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

    let wasmTable;
    const pq = await getPq();

    if (this.useStreaming && this.parquetFile) {
      wasmTable = await this.parquetFile.read({ rowGroups: [rowGroupIndex] });
    } else {
      wasmTable = pq.readParquet(this.parquetData, { rowGroups: [rowGroupIndex] });
    }

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
