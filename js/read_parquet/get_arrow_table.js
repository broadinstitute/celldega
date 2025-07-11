import { handleAsyncError } from '../temp_utils/errorHandler';

import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

export const get_arrow_table = async (url, fetch_options, aws) => {
  console.log('start get_arrow_table func');
  try {
    console.log('start response');
    console.log('url', url);

    const response =
      aws !== null ? await aws.fetch(url) : await fetch(url, fetch_options);
    console.log('after response');

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
