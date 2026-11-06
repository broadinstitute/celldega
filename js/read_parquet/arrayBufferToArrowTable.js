import * as arrow from 'apache-arrow';

import { handleAsyncError } from '../temp_utils/errorHandler';

import { getPq } from './pqInitializer';

/** Consume a parquet-wasm table while keeping each batch's dictionary values. */
export const wasmTableToArrowTable = (wasmTable) => {
  let consumed = false;
  try {
    if (wasmTable.numBatches < 2) {
      consumed = true;
      return arrow.tableFromIPC(wasmTable.intoIPCStream());
    }

    const first = arrow.tableFromIPC(wasmTable.recordBatch(0).intoIPCStream());
    if (first.schema.dictionaries.size === 0) {
      // Geometry and expression tables need no dictionary workaround.
      consumed = true;
      return arrow.tableFromIPC(wasmTable.intoIPCStream());
    }

    // Arrow JS 15 ignores replacement dictionaries in a single IPC stream.
    // parquet-wasm can assign new category codes in every record batch, so
    // decode each batch with its own dictionary registry before joining them.
    const batches = [...first.batches];
    for (let index = 1; index < wasmTable.numBatches; index++) {
      batches.push(
        ...arrow.tableFromIPC(wasmTable.recordBatch(index).intoIPCStream())
          .batches
      );
    }
    return new arrow.Table(first.schema, batches);
  } finally {
    // intoIPCStream consumes its table, including when serialization fails.
    // The per-batch path leaves the parent table owned by this function.
    if (!consumed) wasmTable.free();
  }
};

export const arrayBufferToArrowTable = async (arrayBuffer) => {
  try {
    const pq = await getPq();
    const arr = new Uint8Array(arrayBuffer);
    const wasmTable = pq.readParquet(arr);
    return wasmTableToArrowTable(wasmTable);
  } catch (error) {
    const result = handleAsyncError(error, {
      messages: {
        unexpected: 'Failed to convert ArrayBuffer to Arrow Table',
      },
      logUnexpected: true,
      throwOnAuth: false,
    });

    // For data processing errors
    throw new Error(result.message);
  }
};
