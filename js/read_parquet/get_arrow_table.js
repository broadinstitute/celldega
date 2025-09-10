import { handleAsyncError } from '../temp_utils/errorHandler';

import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

export const get_arrow_table = async (url, fetch_options, aws) => {
  try {

    // console.log('aws:', aws);

    const response =
      aws !== null ? await aws.fetch(url) : await fetch(url, fetch_options);


    // const response = await fetch(url, fetch_options);

    console.log('arrayBuffer')
    const arrayBuffer = await response.arrayBuffer();
    console.log('arrowTable');
    const arrowTable = arrayBufferToArrowTable(arrayBuffer);
    console.log('return arrowTable')
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
