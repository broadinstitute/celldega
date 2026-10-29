import { concatenate_polygon_data } from '../vector_tile/concatenate_functions';

/**
 * Extract polygon data from a single data chunk
 * @param {Object} polygonChunk - The polygon level chunk data
 * @param {Object} ringChunk - The ring level chunk data
 * @param {Object} coordChunk - The coordinate level chunk data
 * @returns {Object|null} - Polygon data object with length, startIndices, and attributes
 */
function getPolygonDataFromChunk(polygonChunk, ringChunk, coordChunk) {
  const polygonOffsets = polygonChunk.valueOffsets;
  const ringOffsets = ringChunk?.valueOffsets;
  const flatCoordinateArray = coordChunk?.values;

  // IPC buffers are padded for alignment. Their capacity can exceed the
  // logical length, and the trailing bytes are not polygon offsets.
  const numPolygons = polygonChunk.length;
  if (
    !polygonOffsets ||
    polygonOffsets.length < numPolygons + 1 ||
    !ringOffsets ||
    !flatCoordinateArray
  ) {
    throw new Error('Invalid polygon geometry: missing coordinate offsets');
  }

  // Build resolved indices: for each polygon, find coordinate start
  const resolvedIndices = new Int32Array(numPolygons + 1);
  let previousRing = -1;
  let previousPoint = -1;
  for (let i = 0; i <= numPolygons; i++) {
    const ringIdx = polygonOffsets[i];
    const pointIdx = ringOffsets[ringIdx];
    if (
      !Number.isInteger(ringIdx) ||
      ringIdx < previousRing ||
      ringIdx < 0 ||
      ringIdx > ringChunk.length ||
      !Number.isInteger(pointIdx) ||
      pointIdx < previousPoint ||
      pointIdx < 0 ||
      pointIdx * 2 > coordChunk.length ||
      pointIdx * 2 > flatCoordinateArray.length
    ) {
      throw new Error(
        'Invalid polygon geometry: coordinate offsets out of bounds'
      );
    }
    resolvedIndices[i] = pointIdx;
    previousRing = ringIdx;
    previousPoint = pointIdx;
  }

  // A sliced Arrow list can reference the middle of its child buffers. Keep
  // only that slice and rebase its offsets before concatenating with tiles.
  const firstPoint = resolvedIndices[0];
  const lastPoint = resolvedIndices[numPolygons];
  const coordinates = new Float64Array(
    flatCoordinateArray.subarray(firstPoint * 2, lastPoint * 2)
  );
  for (let i = 0; i < coordinates.length; i++) {
    if (!Number.isFinite(coordinates[i])) {
      throw new Error('Invalid polygon geometry: non-finite coordinate');
    }
  }
  for (let i = 0; i < resolvedIndices.length; i++) {
    resolvedIndices[i] -= firstPoint;
  }

  return {
    length: numPolygons,
    startIndices: resolvedIndices,
    attributes: {
      getPolygon: { value: coordinates, size: 2 },
    },
  };
}

export const get_polygon_data = (arrowTable) => {
  // Get geometry column by name (more robust than index)
  // Try common column names for geometry data
  const geometryColumn =
    arrowTable.getChild('GEOMETRY') ||
    arrowTable.getChild('geometry') ||
    arrowTable.getChildAt(0);

  if (!geometryColumn) {
    // console.warn('[get_polygon_data] No geometry column found');
    return null;
  }

  // Check if this is the expected nested list type (typeId 12 = List)
  if (geometryColumn.data[0]?.type.typeId !== 12) {
    return null;
  }

  const dataChunks = geometryColumn.data;
  const numChunks = dataChunks.length;

  // Follow each chunk's own children so sliced or empty chunks cannot shift
  // the association between polygon offsets and their coordinate buffers.
  const extractChunk = (polygonChunk) => {
    const ringChunk = polygonChunk.children[0];
    const coordChunk = ringChunk?.children[0]?.children[0];
    return getPolygonDataFromChunk(polygonChunk, ringChunk, coordChunk);
  };

  // For single chunk (original behavior), use direct extraction
  if (numChunks === 1) {
    return extractChunk(dataChunks[0]);
  }

  // Multi-chunk handling (multiple row groups)
  // Process each chunk separately, then concatenate using proven logic
  const chunkPolygonData = [];

  for (let chunkIdx = 0; chunkIdx < numChunks; chunkIdx++) {
    const polygonChunk = dataChunks[chunkIdx];

    // Skip empty chunks
    if (polygonChunk.length === 0) {
      continue;
    }

    const chunkData = extractChunk(polygonChunk);
    if (chunkData && chunkData.length > 0) {
      chunkPolygonData.push(chunkData);
    }
  }

  // Use the same concatenation logic as the non-row-group approach
  return concatenate_polygon_data(chunkPolygonData);
};
