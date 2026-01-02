export const get_polygon_data = (arrowTable) => {
  // Get geometry column by name (more robust than index)
  // Try common column names for geometry data
  let geometryColumn = arrowTable.getChild('GEOMETRY') || 
                       arrowTable.getChild('geometry') ||
                       arrowTable.getChildAt(0);

  if (!geometryColumn) {
    console.warn('[get_polygon_data] No geometry column found');
    return null;
  }

  // Check if this is the expected nested list type (typeId 12 = List)
  if (geometryColumn.data[0].type.typeId !== 12) {
    return null;
  }

  const dataChunks = geometryColumn.data;
  const numChunks = dataChunks.length;
  
  // For single chunk (original behavior), use optimized path
  if (numChunks === 1) {
    const polygonIndices = dataChunks[0].valueOffsets;
    const ringIndices = geometryColumn.getChildAt(0).data[0].valueOffsets;
    const flatCoordinateVector = geometryColumn
      .getChildAt(0)
      .getChildAt(0)
      .getChildAt(0);
    const flatCoordinateArray = flatCoordinateVector.data[0].values;
    const resolvedIndices = new Int32Array(polygonIndices.length);

    for (let i = 0; i < resolvedIndices.length; ++i) {
      resolvedIndices[i] = ringIndices[polygonIndices[i]];
    }

    return {
      length: arrowTable.numRows,
      startIndices: resolvedIndices,
      attributes: {
        getPolygon: { value: flatCoordinateArray, size: 2 },
      },
    };
  }
  
  // Multi-chunk handling (multiple row groups)
  // We need to process each chunk and accumulate offsets
  
  // 1. Merge flat coordinates from all chunks
  const coordVector = geometryColumn.getChildAt(0).getChildAt(0).getChildAt(0);
  const flatCoordinateArray = coordVector.data
    .map((chunk) => chunk.values)
    .reduce((acc, val) => {
      const combined = new Float64Array(acc.length + val.length);
      combined.set(acc);
      combined.set(val, acc.length);
      return combined;
    }, new Float64Array(0));
  
  // 2. Build resolved indices for each polygon across all chunks
  // Process chunk by chunk, tracking global offsets
  const resolvedIndicesList = [];
  
  let globalRingOffset = 0;  // Cumulative ring count from previous chunks
  let globalCoordOffset = 0; // Cumulative coordinate count from previous chunks
  
  const ringChild = geometryColumn.getChildAt(0);
  const coordChild = geometryColumn.getChildAt(0).getChildAt(0).getChildAt(0);
  
  for (let chunkIdx = 0; chunkIdx < numChunks; chunkIdx++) {
    const polygonChunk = dataChunks[chunkIdx];
    const ringChunk = ringChild.data[chunkIdx];
    const coordChunk = coordChild.data[chunkIdx];
    
    const polygonOffsets = polygonChunk.valueOffsets;
    const ringOffsets = ringChunk.valueOffsets;
    
    // For each polygon in this chunk (excluding the final "end" offset)
    const numPolygonsInChunk = polygonOffsets.length - 1;
    for (let i = 0; i < numPolygonsInChunk; i++) {
      // Get the ring index for this polygon (local to chunk)
      const localRingIdx = polygonOffsets[i];
      // Get the coordinate index for this ring (local to chunk)
      const localCoordIdx = ringOffsets[localRingIdx];
      // Add global offset to get absolute coordinate index
      resolvedIndicesList.push(globalCoordOffset + localCoordIdx);
    }
    
    // Update global offsets for next chunk
    // The last value in ringOffsets tells us total rings in this chunk
    globalRingOffset += ringChunk.length;
    // The last value in coordChunk.values tells us total coords in this chunk
    globalCoordOffset += coordChunk.values.length;
  }
  
  // Add final index (pointing past the last coordinate)
  resolvedIndicesList.push(flatCoordinateArray.length / 2);
  
  const resolvedIndices = new Int32Array(resolvedIndicesList);

  return {
    length: arrowTable.numRows,
    startIndices: resolvedIndices,
    attributes: {
      getPolygon: { value: flatCoordinateArray, size: 2 },
    },
  };
};
