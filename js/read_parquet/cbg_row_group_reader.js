/**
 * CBGRowGroupReader - Reads gene expression data from row-grouped parquet files
 *
 * Supports both single file mode (legacy) and chunked file mode.
 * Each gene is stored as a separate row group, enabling efficient access to
 * individual gene expression data without loading the entire file.
 */

import * as arrow from 'apache-arrow';

import { getPq } from './pqInitializer';

/**
 * CBGRowGroupReader class for efficient gene-based expression data access
 */
export class CBGRowGroupReader {
  /**
   * Create a new CBGRowGroupReader
   * @param {string} baseUrl - Base URL for landscape files
   * @param {string|Object} cbgConfig - Either a URL string (legacy) or chunk config object
   */
  constructor(baseUrl, cbgConfig) {
    this.baseUrl = baseUrl;
    this.initialized = false;
    this.useStreaming = true;

    // Determine mode: chunked or single file
    if (typeof cbgConfig === 'string') {
      // Legacy single file mode
      this.chunkedMode = false;
      this.url = `${baseUrl}/${cbgConfig}`;
      this.parquetFile = null;
      this.geneToRowGroup = null; // Will be loaded from file metadata
    } else if (typeof cbgConfig === 'object' && cbgConfig.files) {
      // Chunked mode
      this.chunkedMode = true;
      this.directory = cbgConfig.directory || 'cbg';
      this.files = cbgConfig.files;
      this.maxRowGroupsPerFile = cbgConfig.max_row_groups_per_file || 2000;
      this.totalRowGroups = cbgConfig.total_row_groups || 0;
      // Gene mapping provided in config - no need to read from file!
      this.geneToRowGroup = cbgConfig.gene_to_row_group || {};
      this.geneList = Object.keys(this.geneToRowGroup);
      // console.log(
      //   `[CBGRowGroupReader] Chunked mode: ${this.files.length} files, ${this.geneList.length} genes`
      // );
    } else {
      throw new Error(
        '[CBGRowGroupReader] Invalid cbgConfig: must be string URL or chunk config object'
      );
    }
  }

  /**
   * Lightweight existence check for a URL (HEAD, or ranged GET fallback).
   * @param {string} url
   * @returns {Promise<boolean>}
   */
  async _resourceExists(url) {
    try {
      let response = await fetch(url, { method: 'HEAD', cache: 'no-store' });
      if (response.status === 405 || response.status === 501) {
        response = await fetch(url, {
          method: 'GET',
          headers: { Range: 'bytes=0-0' },
          cache: 'no-store',
        });
      }
      return response.ok || response.status === 206;
    } catch {
      return false;
    }
  }

  /**
   * When landscape_parameters points at a legacy single file (e.g. cbg.parquet) but
   * preprocessing only produced chunked row-group files under cbg/, discover layout
   * from cbg/chunk_0.parquet schema metadata (same keys as Python writer).
   * @param {*} pq - parquet-wasm module from getPq()
   * @returns {Promise<null|{
   *   directory: string,
   *   files: string[],
   *   maxRowGroupsPerFile: number,
   *   totalRowGroups: number,
   *   geneToRowGroup: Record<string, number>,
   *   geneList: string[],
   * }>}
   */
  async _discoverChunkedCbgFromDefaultDirectory(pq) {
    const probeUrl = `${this.baseUrl}/cbg/chunk_0.parquet`;
    if (!(await this._resourceExists(probeUrl))) {
      return null;
    }

    const parquetFile = await pq.ParquetFile.fromUrl(probeUrl);
    const wasmTable = await parquetFile.read({ rowGroups: [0] });
    const arrowIPC = wasmTable.intoIPCStream();
    const arrowTable = arrow.tableFromIPC(arrowIPC);
    const schemaMetadata = arrowTable.schema.metadata;

    if (!schemaMetadata || !schemaMetadata.has('gene_to_row_group')) {
      return null;
    }

    const geneMapJson = schemaMetadata.get('gene_to_row_group');
    const geneToRowGroup = JSON.parse(geneMapJson);
    const geneList = Object.keys(geneToRowGroup);

    let numGenes = geneList.length;
    if (schemaMetadata.has('num_genes')) {
      const parsed = parseInt(schemaMetadata.get('num_genes'), 10);
      if (!Number.isNaN(parsed) && parsed > 0) {
        numGenes = parsed;
      }
    }

    let maxRowGroupsPerFile = 2000;
    if (schemaMetadata.has('max_row_groups_per_file')) {
      const parsed = parseInt(
        schemaMetadata.get('max_row_groups_per_file'),
        10
      );
      if (!Number.isNaN(parsed) && parsed > 0) {
        maxRowGroupsPerFile = parsed;
      }
    }

    const numFiles = Math.max(1, Math.ceil(numGenes / maxRowGroupsPerFile));
    const files = Array.from(
      { length: numFiles },
      (_, i) => `chunk_${i}.parquet`
    );

    return {
      directory: 'cbg',
      files,
      maxRowGroupsPerFile,
      totalRowGroups: numGenes,
      geneToRowGroup,
      geneList,
    };
  }

  /**
   * Check if the server supports Range requests (needed for streaming)
   * @param {string} url - URL to check
   * @returns {Promise<boolean>}
   */
  async _checkRangeSupport(url) {
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
        // console.log(
        //   `[CBGRowGroupReader] Range check failed with status ${response.status}`
        // );
        return false;
      }

      const footerResponse = await fetch(url, {
        method: 'GET',
        headers: { Range: 'bytes=-8' },
      });

      if (!footerResponse.ok && footerResponse.status !== 206) {
        // console.log(
        //   `[CBGRowGroupReader] Footer range check failed with status ${footerResponse.status}`
        // );
        return false;
      }

      const isPartial =
        response.status === 206 && footerResponse.status === 206;
      return isPartial || response.headers.get('Accept-Ranges') === 'bytes';
    } catch {
      // Range check failed
      return false;
    }
  }

  /**
   * Compute which chunk file contains a given global row group index
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
   * Get a ParquetFile for a specific chunk (lazy loading)
   * @param {number} fileIndex - Index of the chunk file
   * @returns {Promise<ParquetFile>}
   */
  async _getParquetFile(fileIndex) {
    const fileName = this.files[fileIndex];
    if (!fileName) {
      throw new Error(
        `[CBGRowGroupReader] No file for index ${fileIndex}. Available: ${this.files.length} files`
      );
    }

    const fileUrl = `${this.baseUrl}/${this.directory}/${fileName}`;
    const pq = await getPq();

    // console.log(`[CBGRowGroupReader] Loading chunk file: ${fileName}`);
    const parquetFile = await pq.ParquetFile.fromUrl(fileUrl);

    return parquetFile;
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

    if (!this.chunkedMode) {
      const legacyExists = await this._resourceExists(this.url);
      if (!legacyExists) {
        const discovered =
          await this._discoverChunkedCbgFromDefaultDirectory(pq);
        if (discovered) {
          this.chunkedMode = true;
          this.directory = discovered.directory;
          this.files = discovered.files;
          this.maxRowGroupsPerFile = discovered.maxRowGroupsPerFile;
          this.totalRowGroups = discovered.totalRowGroups;
          this.geneToRowGroup = discovered.geneToRowGroup;
          this.geneList = discovered.geneList;
          this.url = null;
          this.parquetFile = null;
        } else {
          throw new Error(
            `[CBGRowGroupReader] CBG not found at ${this.url} and could not find ` +
              `chunked data at ${this.baseUrl}/cbg/chunk_0.parquet. ` +
              `Fix landscape_parameters row_group_files.cbg or add the missing file.`
          );
        }
      }
    }

    if (!this.chunkedMode) {
      // Single file mode - check range support and load file
      const rangeSupported = await this._checkRangeSupport(this.url);

      if (!rangeSupported) {
        throw new Error(
          `[CBGRowGroupReader] Range requests not supported for ${this.url}. ` +
            `Row group mode requires a server that supports HTTP Range requests with CORS.`
        );
      }

      if (!pq.ParquetFile || typeof pq.ParquetFile.fromUrl !== 'function') {
        throw new Error(
          `[CBGRowGroupReader] ParquetFile.fromUrl not available. ` +
            `Please ensure parquet-wasm is properly initialized.`
        );
      }

      // console.log(
      //   `[CBGRowGroupReader] Range requests supported, creating streaming ParquetFile...`
      // );
      this.parquetFile = await pq.ParquetFile.fromUrl(this.url);
      this.useStreaming = true;

      const metadata = this.parquetFile.metadata();
      const numRowGroups = metadata.numRowGroups();
      // console.log(
      //   `[CBGRowGroupReader] Streaming mode enabled, ${numRowGroups} row groups available`
      // );

      this.numRowGroups = numRowGroups;
      // Gene index will be loaded lazily on first request
      this.geneToRowGroup = null;
      this.geneList = null;

      // console.log(`[CBGRowGroupReader] Initialized with lazy gene index loading`);
    } else {
      // Chunked mode - just check range support on first file
      const firstFileUrl = `${this.baseUrl}/${this.directory}/${this.files[0]}`;
      const rangeSupported = await this._checkRangeSupport(firstFileUrl);

      if (!rangeSupported) {
        throw new Error(
          `[CBGRowGroupReader] Range requests not supported. ` +
            `Row group mode requires a server that supports HTTP Range requests with CORS.`
        );
      }

      // console.log(
      //   `[CBGRowGroupReader] Chunked mode enabled: ${this.files.length} files, ` +
      //     `${this.geneList.length} genes`
      // );
    }

    this.initialized = true;
  }

  /**
   * Ensure gene index is loaded (lazy loading for single file mode)
   * @returns {Promise<void>}
   */
  async _ensureGeneIndex() {
    if (this.geneToRowGroup !== null) {
      return; // Already loaded
    }

    // console.log(`[CBGRowGroupReader] Building gene index lazily...`);

    // Try to read metadata from row group 0
    try {
      // console.log(`[CBGRowGroupReader] Reading row group 0 for schema metadata...`);
      const wasmTable = await this.parquetFile.read({ rowGroups: [0] });
      const arrowIPC = wasmTable.intoIPCStream();
      const arrowTable = arrow.tableFromIPC(arrowIPC);

      // Check if schema has gene_to_row_group metadata
      const schemaMetadata = arrowTable.schema.metadata;
      if (schemaMetadata && schemaMetadata.has('gene_to_row_group')) {
        const geneMapJson = schemaMetadata.get('gene_to_row_group');
        this.geneToRowGroup = JSON.parse(geneMapJson);
        this.geneList = Object.keys(this.geneToRowGroup);
        // console.log(
        //   `[CBGRowGroupReader] Loaded gene index from metadata: ${this.geneList.length} genes`
        // );
        return;
      }
    } catch {
      // console.log(
      //   `[CBGRowGroupReader] Could not read metadata from row group 0: ${error.message}`
      // );
    }

    // Fallback: build index by reading each row group (slow for large files)
    // console.log(`[CBGRowGroupReader] Building gene index manually (this may be slow)...`);
    this.geneToRowGroup = await this._buildGeneIndex(this.numRowGroups);
    this.geneList = Object.keys(this.geneToRowGroup);
    // console.log(`[CBGRowGroupReader] Built gene index: ${this.geneList.length} genes`);
  }

  /**
   * Build gene index by reading each row group's gene column
   * @param {number} numRowGroups - Number of row groups in the file
   * @returns {Promise<Object>} - Map from gene name to row group index
   */
  async _buildGeneIndex(numRowGroups) {
    const index = {};

    // Note: Sequential reads are intentional here - reading all row groups in parallel
    // would cause memory issues for large files. This is a one-time index build.
    for (let i = 0; i < numRowGroups; i++) {
      try {
        // eslint-disable-next-line no-await-in-loop
        const table = await this.parquetFile.read({ rowGroups: [i] });
        const arrowIPC = table.intoIPCStream();
        const arrowTable = arrow.tableFromIPC(arrowIPC);

        const geneCol = arrowTable.getChild('gene');
        if (geneCol && geneCol.length > 0) {
          const geneName = geneCol.get(0);
          index[geneName] = i;
        }
      } catch {
        // console.warn(
        //   `[CBGRowGroupReader] Error reading row group ${i}:`,
        //   error
        // );
      }
    }

    // console.log(
    //   `[CBGRowGroupReader] Built index for ${Object.keys(index).length} genes`
    // );
    return index;
  }

  /**
   * Check if a gene exists in the dataset
   * @param {string} geneName - Gene name to check
   * @returns {Promise<boolean>}
   */
  async hasGene(geneName) {
    await this._ensureGeneIndex();
    return geneName in this.geneToRowGroup;
  }

  /**
   * Get the row group index for a gene
   * @param {string} geneName - Gene name
   * @returns {Promise<number|null>} - Row group index or null if not found
   */
  async getGeneRowGroupIndex(geneName) {
    await this._ensureGeneIndex();
    return this.geneToRowGroup[geneName] ?? null;
  }

  /**
   * Read expression data for a specific gene
   * @param {string} geneName - Gene name to read
   * @returns {Promise<arrow.Table|null>} - Arrow Table with expression data
   */
  async readGene(geneName) {
    if (!this.initialized) {
      await this.initialize();
    }

    await this._ensureGeneIndex();

    const globalRowGroupIndex = this.geneToRowGroup[geneName];
    if (globalRowGroupIndex === undefined) {
      // console.warn(`[CBGRowGroupReader] Gene not found: ${geneName}`);
      return null;
    }

    try {
      if (!this.chunkedMode) {
        // Single file mode
        const wasmTable = await this.parquetFile.read({
          rowGroups: [globalRowGroupIndex],
        });
        const arrowIPC = wasmTable.intoIPCStream();
        return arrow.tableFromIPC(arrowIPC);
      } else {
        // Chunked mode - find the right file
        const { fileIndex, localIndex } =
          this.computeChunkLocation(globalRowGroupIndex);
        const pqFile = await this._getParquetFile(fileIndex);
        const wasmTable = await pqFile.read({ rowGroups: [localIndex] });
        const arrowIPC = wasmTable.intoIPCStream();
        return arrow.tableFromIPC(arrowIPC);
      }
    } catch {
      // console.error(`[CBGRowGroupReader] Error reading gene ${geneName}:`, error);
      return null;
    }
  }

  /**
   * Get total number of genes
   * @returns {Promise<number>}
   */
  async getNumGenes() {
    await this._ensureGeneIndex();
    return this.geneList.length;
  }

  /**
   * Get list of all gene names
   * @returns {Promise<string[]>}
   */
  async getGeneNames() {
    await this._ensureGeneIndex();
    return [...this.geneList];
  }
}
