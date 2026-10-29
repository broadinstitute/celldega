export const concatenate_polygon_data = (dataObjects) => {
  const startIndices = [0];
  const spans = [];
  let coordinateCount = 0;

  for (const data of dataObjects) {
    if (!data) {
      continue;
    }
    if (!Number.isSafeInteger(data.length) || data.length < 0) {
      throw new Error('Invalid polygon row count');
    }

    const offsets = data.startIndices || [];
    const coordinates = data.attributes?.getPolygon?.value || [];

    // Arrow buffers may contain unused prefixes, suffixes or alignment padding.
    // Copy only the logical rows. Invalid spans must not reach PathLayer, where
    // they can turn unrelated cells into a single connected path.
    for (let i = 0; i < data.length; i++) {
      const start = offsets[i];
      const end = offsets[i + 1];
      if (
        !Number.isSafeInteger(start) ||
        !Number.isSafeInteger(end) ||
        start < 0 ||
        end < start ||
        end > coordinates.length / 2
      ) {
        throw new Error(`Invalid polygon coordinate offsets at row ${i}`);
      }
      spans.push({ coordinates, start: start * 2, end: end * 2 });
      coordinateCount += (end - start) * 2;
      startIndices.push(coordinateCount / 2);
    }
  }

  const value = new Float64Array(coordinateCount);
  let offset = 0;
  for (const span of spans) {
    const coordinates = span.coordinates.subarray
      ? span.coordinates.subarray(span.start, span.end)
      : span.coordinates.slice(span.start, span.end);
    value.set(coordinates, offset);
    offset += coordinates.length;
  }

  return {
    length: startIndices.length - 1,
    startIndices: new Int32Array(startIndices),
    attributes: { getPolygon: { value, size: 2 } },
  };
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
