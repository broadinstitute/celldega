export const get_polygon_data = (arrowTable) => {

  const geometryColumn = arrowTable.getChildAt(0)

  if (geometryColumn.data[0].type.typeId === 12){

    const polygonIndices = geometryColumn.data[0].valueOffsets
    const ringIndices = geometryColumn.getChildAt(0).data[0].valueOffsets
    const flatCoordinateVector = geometryColumn.getChildAt(0).getChildAt(0).getChildAt(0)
    const flatCoordinateArray = flatCoordinateVector.data[0].values
    const resolvedIndices = new Int32Array(polygonIndices.length);

    for (let i = 0; i < resolvedIndices.length; ++i) {
      // Perform the lookup into the ringIndices array using the polygonIndices array
      resolvedIndices[i] = ringIndices[polygonIndices[i]]
    }

    const data = {
      // Number of geometries
      length: arrowTable.numRows,
      // Indices into coordinateArray where each polygon starts
      startIndices: resolvedIndices,
      // Flat coordinates array
      attributes: {
        getPolygon: { value: flatCoordinateArray, size: 2 }
      }
    }
    return data
  } else {
    return null
  }
}