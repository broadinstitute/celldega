import { handleAsyncError } from '../temp_utils/errorHandler';

import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

export const get_arrow_table = async (url, fetch_options, aws) => {
  try {
    const fetchFn =
      aws && typeof aws.fetch === 'function' ? aws.fetch.bind(aws) : fetch;

    const response = await fetchFn(url, fetch_options);

    const arrayBuffer = await response.arrayBuffer();
    const arrowTable = arrayBufferToArrowTable(arrayBuffer);
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
