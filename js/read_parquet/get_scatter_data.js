import { handleAsyncError } from '../temp_utils/errorHandler';

export const get_scatter_data = (arrow_table) => {
  try {
    const geometry = arrow_table.getChild('geometry').toArray();

    const size = geometry[0].length || 2;
    const flatCoordinateArray = new Float64Array(geometry.length * size);

    geometry.forEach((coords, index) => {
      flatCoordinateArray.set(coords, index * size);
    });

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
    return [];
  }
};
