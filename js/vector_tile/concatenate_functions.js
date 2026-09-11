export const concatenate_polygon_data = (dataObjects) => {
  // Filter out undefined or null elements
  dataObjects = dataObjects.filter(
    (data) => data !== undefined && data !== null
  );

  const separated = Boolean(
    dataObjects[0]?.attributes?.getPolygonX &&
      dataObjects[0]?.attributes?.getPolygonY
  );

  // Initialize concatenated data structure
  const concatenatedData = {
    length: 0,
    startIndices: new Int32Array(),
    attributes: separated
      ? {
          getPolygonX: { value: new Float64Array(), size: 1 },
          getPolygonY: { value: new Float64Array(), size: 1 },
        }
      : {
          getPolygon: {
            value: new Float64Array(),
            size: 2,
          },
        },
  };

  // Iterate over each data object to combine them
  dataObjects.forEach((data, index) => {
    concatenatedData.length += data.length;

    // Handle startIndices
    const lastValue = separated
      ? concatenatedData.attributes.getPolygonX.value.length
      : concatenatedData.attributes.getPolygon.value.length / 2;
    let adjustedStartIndices = data.startIndices;

    if (index > 0) {
      // Adjust startIndices (except for the first data object)
      adjustedStartIndices = new Int32Array(data.startIndices.length);
      for (let i = 0; i < data.startIndices.length; i++) {
        adjustedStartIndices[i] = data.startIndices[i] + lastValue;
      }
    }

    // Combine startIndices and coordinate values
    concatenatedData.startIndices = new Int32Array([
      ...concatenatedData.startIndices,
      ...adjustedStartIndices.slice(index > 0 ? 1 : 0),
    ]);
    if (separated) {
      concatenatedData.attributes.getPolygonX.value = new Float64Array([
        ...concatenatedData.attributes.getPolygonX.value,
        ...data.attributes.getPolygonX.value,
      ]);
      concatenatedData.attributes.getPolygonY.value = new Float64Array([
        ...concatenatedData.attributes.getPolygonY.value,
        ...data.attributes.getPolygonY.value,
      ]);
    } else {
      concatenatedData.attributes.getPolygon.value = new Float64Array([
        ...concatenatedData.attributes.getPolygon.value,
        ...data.attributes.getPolygon.value,
      ]);
    }
  });

  return concatenatedData;
};

export const concatenate_arrow_tables = (tables) => {
  if (tables.length === 0) return null; // No tables to concatenate
  let baseTable = tables[0]; // Use the first table as the base
  for (let i = 1; i < tables.length; i++) {
    // Start from the second table
    baseTable = baseTable.concat(tables[i]); // Concatenate each table to the base table
  }
  return baseTable;
};
