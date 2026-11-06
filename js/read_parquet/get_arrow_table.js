import { handleAsyncError } from '../temp_utils/errorHandler';

import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

export const get_arrow_table = async (url, fetch_options, aws) => {
  try {
    const response =
      aws !== null ? await aws.fetch(url) : await fetch(url, fetch_options);

    if (!response.ok) {
      const error = new Error(`Request failed with status ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const arrayBuffer = await response.arrayBuffer();
    // Await here so a parse failure (e.g. an HTML error body from a 404)
    // is caught below instead of becoming an unhandled promise rejection.
    const arrowTable = await arrayBufferToArrowTable(arrayBuffer);
    return arrowTable;
  } catch (error) {
    handleAsyncError(error, {
      context: 'loading arrow table data',
      url,
      logUnexpected: true,
      throwOnAuth: false,
    });
    return [];
  }
};
