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
    const flatCoordinateArray = arrow_table
      .getChild('geometry')
      .getChildAt(0)
      .data.map((x) => x.values)
      .reduce((acc, val) => {
        const combined = new Float64Array(acc.length + val.length);
        combined.set(acc);
        combined.set(val, acc.length);
        return combined;
      }, new Float64Array(0));

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
