/**
 * Proof of Concept: Reading row-grouped Parquet files with parquet-wasm 0.7.1
 *
 * This module demonstrates how to:
 * 1. Read metadata to discover row groups
 * 2. Read specific row groups on demand
 * 3. Stream data efficiently
 *
 * Usage: Import and call testRowGroupReading() with a URL to a row-grouped parquet file
 */

import * as arrow from 'apache-arrow';

import { readParquetWithOptions, getVersion, getPq } from './pqInitializer';

/**
 * Fetch a parquet file and read specific row groups
 * @param {string} url - URL to the parquet file
 * @param {number[]} rowGroups - Array of row group indices to read (optional, reads all if not specified)
 * @returns {Promise<arrow.Table>} - Arrow Table with the requested data
 */
export async function readRowGroups(url, rowGroups = null) {
  console.log(`[row_group_poc] Fetching parquet file from: ${url}`);

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch parquet file: ${response.statusText}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  const data = new Uint8Array(arrayBuffer);

  console.log(
    `[row_group_poc] Parquet file size: ${(data.length / 1024).toFixed(2)} KB`
  );

  // Read with row group options
  const options = rowGroups ? { rowGroups } : {};
  console.log(`[row_group_poc] Reading with options:`, options);

  const wasmTable = readParquetWithOptions(data, options);
  const arrowIPC = wasmTable.intoIPCStream();
  const table = arrow.tableFromIPC(arrowIPC);

  console.log(
    `[row_group_poc] Read ${table.numRows} rows, ${table.numCols} columns`
  );
  console.log(
    `[row_group_poc] Schema:`,
    table.schema.fields.map((f) => f.name)
  );

  return table;
}

/**
 * Get metadata about a parquet file's row groups
 * @param {string} url - URL to the parquet file
 * @returns {Promise<Object>} - Metadata including row group info
 */
export async function getParquetMetadata(url) {
  const pq = await getPq();

  console.log(`[row_group_poc] Fetching metadata from: ${url}`);

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch parquet file: ${response.statusText}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  const data = new Uint8Array(arrayBuffer);

  // Read the full table to get metadata (parquet-wasm 0.7.1 doesn't expose metadata directly yet)
  // In a future version, we might use ParquetFile.fromUrl() for streaming metadata
  const wasmTable = pq.readParquet(data);
  const {numBatches} = wasmTable;
  const {schema} = wasmTable;

  // Get schema as IPC to read in JS
  const schemaIPC = schema.intoIPCStream();
  const arrowSchema = arrow.tableFromIPC(schemaIPC).schema;

  return {
    numBatches,
    columns: arrowSchema.fields.map((f) => ({
      name: f.name,
      type: f.type.toString(),
    })),
  };
}

/**
 * Test function to demonstrate row group reading
 * Call this from landscape_ist.js or browser console
 *
 * @param {string} url - URL to a row-grouped parquet file
 */
// Re-export version function
export { getVersion } from './pqInitializer';

export async function testRowGroupReading(url) {
  console.log('='.repeat(60));
  console.log('[row_group_poc] Starting Row Group Reading Test');
  console.log(`[row_group_poc] parquet-wasm version: ${getVersion()}`);
  console.log('='.repeat(60));

  try {
    // Test 1: Read all data
    console.log('\n[Test 1] Reading ALL row groups:');
    const allData = await readRowGroups(url);
    console.log(`  Total rows: ${allData.numRows}`);

    // Sample first few rows
    const firstBatch = allData.batches[0];
    if (firstBatch) {
      console.log('  First 3 rows sample:');
      for (let i = 0; i < Math.min(3, firstBatch.numRows); i++) {
        const row = {};
        for (const field of allData.schema.fields) {
          const col = firstBatch.getChild(field.name);
          row[field.name] = col ? col.get(i) : null;
        }
        console.log(`    Row ${i}:`, row);
      }
    }

    // Test 2: Read only specific row groups
    console.log('\n[Test 2] Reading ONLY row group 0:');
    const group0 = await readRowGroups(url, [0]);
    console.log(`  Rows from group 0: ${group0.numRows}`);

    // Test 3: Read multiple specific row groups
    console.log('\n[Test 3] Reading row groups 0 and 2:');
    const groups02 = await readRowGroups(url, [0, 2]);
    console.log(`  Rows from groups 0,2: ${groups02.numRows}`);

    // Verify by checking row_group_id column if present
    const rgIdCol = groups02.getChild('row_group_id');
    if (rgIdCol) {
      const uniqueGroupIds = new Set();
      for (let i = 0; i < rgIdCol.length; i++) {
        uniqueGroupIds.add(rgIdCol.get(i));
      }
      console.log(
        `  Row group IDs present: [${[...uniqueGroupIds].sort().join(', ')}]`
      );
    }

    console.log(`\n${  '='.repeat(60)}`);
    console.log('[row_group_poc] Test completed successfully!');
    console.log('='.repeat(60));

    return { allData, group0, groups02 };
  } catch (error) {
    console.error('[row_group_poc] Test failed:', error);
    throw error;
  }
}

// Export for use in other modules
export default {
  readRowGroups,
  getParquetMetadata,
  testRowGroupReading,
  getVersion,
};
