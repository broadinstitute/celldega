import { Type } from 'apache-arrow';

export const get_polygon_data = (arrowTable) => {
  const geometryColumn = arrowTable.getChildAt(0);
  const typeId = geometryColumn.data[0].type.typeId;

  if (typeId === Type.List) {
    const polygonIndices = geometryColumn.data[0].valueOffsets;
    const ringIndices = geometryColumn.getChildAt(0).data[0].valueOffsets;
    const flatCoordinateVector = geometryColumn
      .getChildAt(0)
      .getChildAt(0)
      .getChildAt(0);
    const flatCoordinateArray = flatCoordinateVector.data[0].values;
    const resolvedIndices = new Int32Array(polygonIndices.length);

    for (let i = 0; i < resolvedIndices.length; ++i) {
      // Perform the lookup into the ringIndices array using the polygonIndices array
      resolvedIndices[i] = ringIndices[polygonIndices[i]];
    }

    const data = {
      // Number of geometries
      length: arrowTable.numRows,
      // Indices into coordinateArray where each polygon starts
      startIndices: resolvedIndices,
      // Flat coordinates array
      attributes: {
        getPolygon: { value: flatCoordinateArray, size: 2 },
      },
    };
    return data;
  } else if (typeId === Type.Utf8) {
    const jsonValues = geometryColumn.toArray();
    const polygons = Array.from(jsonValues, (d) => JSON.parse(d));

    const start = new Int32Array(polygons.length + 1);
    const coords = [];
    let offset = 0;

    for (let i = 0; i < polygons.length; i++) {
      start[i] = offset;
      const rings = polygons[i];
      if (rings.length > 0) {
        const firstRing = rings[0];
        for (const [x, y] of firstRing) {
          coords.push(x, y);
          offset += 1;
        }
      }
    }
    start[polygons.length] = offset;

    return {
      length: polygons.length,
      startIndices: start,
      attributes: { getPolygon: { value: new Float64Array(coords), size: 2 } },
    };
  } else {
    return null;
  }
};
