export const extractPolygonPaths = (data) => {
  const paths = [];
  if (!data || !Number.isSafeInteger(data.length) || data.length < 0) {
    throw new Error('Invalid polygon row count');
  }
  const startIndices = data.startIndices || [];
  const coordinates = data.attributes?.getPolygon?.value || [];

  for (let i = 0; i < data.length; ++i) {
    const path = [];
    const start = startIndices[i];
    const end = startIndices[i + 1];
    if (
      !Number.isSafeInteger(start) ||
      !Number.isSafeInteger(end) ||
      start < 0 ||
      end < start ||
      end > coordinates.length / 2
    ) {
      throw new Error(`Invalid polygon coordinate offsets at row ${i}`);
    }

    for (let j = start * 2; j < end * 2; j += 2) {
      const x = coordinates[j];
      const y = coordinates[j + 1];
      // Dropping a bad vertex would join its neighbors across a missing span.
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        throw new Error(`Invalid polygon coordinate at row ${i}`);
      }
      path.push([x, y]);
    }

    paths.push(path);
  }

  return paths;
};
