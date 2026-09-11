import { concatenate_polygon_data } from '../vector_tile/concatenate_functions';

/**
 * Extract polygon data from a single data chunk
 * @param {Object} polygonChunk - The polygon level chunk data
 * @param {Object} ringChunk - The ring level chunk data
 * @param {Object} coordChunk - The coordinate level chunk data
 * @returns {Object|null} - Polygon data object with length, startIndices, and attributes
 */
function getPolygonDataFromChunk(
  polygonChunk,
  ringChunk,
  coordChunk,
  yCoordChunk = null
) {
  const polygonOffsets = polygonChunk.valueOffsets;
  const ringOffsets = ringChunk.valueOffsets;

  // Number of polygons is offsets length - 1
  const numPolygons = polygonOffsets.length - 1;

  // Build resolved indices: for each polygon, find coordinate start
  const resolvedIndices = new Int32Array(polygonOffsets.length);
  for (let i = 0; i < polygonOffsets.length; i++) {
    const ringIdx = polygonOffsets[i];
    resolvedIndices[i] = ringOffsets[ringIdx];
  }

  const attributes = yCoordChunk
    ? {
        getPolygonX: { value: coordChunk.values, size: 1 },
        getPolygonY: { value: yCoordChunk.values, size: 1 },
      }
    : { getPolygon: { value: coordChunk.values, size: 2 } };

  return {
    length: numPolygons,
    startIndices: resolvedIndices,
    attributes,
  };
}

// apache-arrow Type ids used below.
const ARROW_LIST = 12;
const ARROW_STRUCT = 13;
const ARROW_FIXED_SIZE_LIST = 16;

/**
 * Extract deck.gl binary polygon data from an Arrow table.
 *
 * The expected layout is polygon -> rings -> interleaved vertex pairs, so the flat
 * coordinate buffer becomes getPolygon and the list offsets become startIndices.
 *
 * The vertex level may be either a List or a FixedSizeList. Parquet has no fixed-size
 * list type, so a writer's `fixed_size_list<n, 2>` is stored as a plain List and only
 * readers that honour the embedded ARROW:schema hint reconstruct the fixed-size type --
 * parquet-wasm does not. Both forms are interleaved and equally usable here.
 *
 * @param {Object} arrowTable - Arrow table holding the geometry column
 * @param {string} [geometryColumnName] - Column to read. Defaults to the DegaFiles
 *   names (GEOMETRY / geometry); a SpatialData profile passes display_geometry.
 * @returns {Object|null} - Polygon data, or null if the column is missing or not in the
 *   expected binary layout
 */
export const get_polygon_data = (arrowTable, geometryColumnName) => {
  // Get geometry column by name (more robust than index)
  // Try common column names for geometry data
  const geometryColumn = geometryColumnName
    ? arrowTable.getChild(geometryColumnName)
    : arrowTable.getChild('GEOMETRY') ||
      arrowTable.getChild('geometry') ||
      arrowTable.getChildAt(0);

  if (!geometryColumn) {
    // console.warn('[get_polygon_data] No geometry column found');
    return null;
  }

  // Check if this is the expected nested list type (typeId 12 = List)
  if (geometryColumn.data[0].type.typeId !== ARROW_LIST) {
    return null;
  }

  const dataChunks = geometryColumn.data;
  const numChunks = dataChunks.length;

  // Get child columns for ring and coordinate data
  const ringChild = geometryColumn.getChildAt(0);
  const vertexChild = ringChild?.getChildAt(0);

  // GeoArrow permits struct<x, y> coordinates, which geopandas emits for canonical
  // Shapes. Keep those child buffers separate; the path conversion already walks every
  // vertex, so it can pair x and y without an additional interleaving allocation.
  const vertexTypeId = vertexChild?.data[0]?.type?.typeId;
  if (
    !vertexChild ||
    ![ARROW_LIST, ARROW_STRUCT, ARROW_FIXED_SIZE_LIST].includes(vertexTypeId)
  ) {
    // console.warn(
    //   `[get_polygon_data] unsupported vertex layout (typeId ${vertexTypeId});` +
    //     ` expected interleaved coordinates, not struct<x, y>`
    // );
    return null;
  }

  const coordChild = vertexChild.getChildAt(0);
  const yCoordChild =
    vertexTypeId === ARROW_STRUCT ? vertexChild.getChildAt(1) : null;
  if (!coordChild || (vertexTypeId === ARROW_STRUCT && !yCoordChild)) {
    return null;
  }

  // For single chunk (original behavior), use direct extraction
  if (numChunks === 1) {
    return getPolygonDataFromChunk(
      dataChunks[0],
      ringChild.data[0],
      coordChild.data[0],
      yCoordChild?.data[0]
    );
  }

  // Multi-chunk handling (multiple row groups)
  // Process each chunk separately, then concatenate using proven logic
  const chunkPolygonData = [];

  for (let chunkIdx = 0; chunkIdx < numChunks; chunkIdx++) {
    const polygonChunk = dataChunks[chunkIdx];
    const ringChunk = ringChild.data[chunkIdx];
    const coordChunk = coordChild.data[chunkIdx];

    // Skip empty chunks
    if (polygonChunk.length === 0) {
      continue;
    }

    const chunkData = getPolygonDataFromChunk(
      polygonChunk,
      ringChunk,
      coordChunk,
      yCoordChild?.data[chunkIdx]
    );
    if (chunkData && chunkData.length > 0) {
      chunkPolygonData.push(chunkData);
    }
  }

  // Use the same concatenation logic as the non-row-group approach
  return concatenate_polygon_data(chunkPolygonData);
};
