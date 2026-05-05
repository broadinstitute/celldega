import { handleAsyncError } from '../temp_utils/errorHandler';

export const get_scatter_data = (arrow_table) => {
  // Handle null or undefined table
  if (!arrow_table) {
    return {
      length: 0,
      attributes: {
        getPosition: { value: new Float32Array(), size: 2 },
      },
    };
  }

  try {
    const geometryColumn = arrow_table.getChild('geometry')?.getChildAt(0);
    const chunks = geometryColumn?.data?.map((x) => x.values) || [];

    const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
    const flatCoordinateArray = new Float64Array(totalLength);

    let offset = 0;
    for (const chunk of chunks) {
      flatCoordinateArray.set(chunk, offset);
      offset += chunk.length;
    }

    const size = flatCoordinateArray.length / arrow_table.numRows;

    const scatter_data = {
      length: arrow_table.numRows,
      attributes: {
        getPosition: { value: flatCoordinateArray, size },
      },
    };

    return scatter_data;
  } catch (error) {
    handleAsyncError(error, {
      context: 'processing scatter data from arrow table',
      logUnexpected: true,
      throwOnAuth: false,
    });
    return {
      length: 0,
      attributes: {
        getPosition: { value: new Float32Array(), size: 2 },
      },
    };
  }
};
