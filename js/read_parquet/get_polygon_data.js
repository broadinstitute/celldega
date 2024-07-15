export const get_polygon_data = (arrowTable) => {

  console.log('arrowTable', arrowTable)

  var geometryColumn = arrowTable.getChildAt(0)

  console.log('geometryColumn data', geometryColumn.data)
  console.log('data[0]', geometryColumn.data[0])
  console.log('type:', geometryColumn.data[0].type)
  console.log('type:', geometryColumn.data[0].type.typeId)
  console.log('-------------')

  if (geometryColumn.data[0].type.typeId === 12){

    var polygonIndices = geometryColumn.data[0].valueOffsets
    var ringIndices = geometryColumn.getChildAt(0).data[0].valueOffsets
    var flatCoordinateVector = geometryColumn.getChildAt(0).getChildAt(0).getChildAt(0)
    var flatCoordinateArray = flatCoordinateVector.data[0].values
    const resolvedIndices = new Int32Array(polygonIndices.length);

    for (let i = 0; i < resolvedIndices.length; ++i) {
      // Perform the lookup into the ringIndices array using the polygonIndices array
      resolvedIndices[i] = ringIndices[polygonIndices[i]]
    }

    var data = {
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
    console.error('NULL!!!')
    // return []
  }
}