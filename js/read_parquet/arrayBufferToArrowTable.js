import * as arrow from 'apache-arrow';

import { handleAsyncError } from '../temp_utils/errorHandler';

import { getPq } from './pqInitializer';

export const arrayBufferToArrowTable = async (arrayBuffer) => {
  try {
    const pq = await getPq();
    const arr = new Uint8Array(arrayBuffer);
    const arrowIPC = pq.readParquet(arr);
    return arrow.tableFromIPC(arrowIPC);
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
