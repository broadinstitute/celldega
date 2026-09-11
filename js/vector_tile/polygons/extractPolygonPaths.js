export const extractPolygonPaths = (data, displayTransform = null) => {
  if (!data) return [];
  const paths = [];
  const { startIndices, attributes } = data;
  const coordinates = attributes.getPolygon?.value;
  const xs = attributes.getPolygonX?.value;
  const ys = attributes.getPolygonY?.value;
  const matrix = displayTransform?.affine_matrix;
  const [a = 1, b = 0, c = 0] = matrix?.[0] || [];
  const [d = 0, e = 1, f = 0] = matrix?.[1] || [];
  const numPolygons = startIndices.length - 1;

  for (let i = 0; i < numPolygons; ++i) {
    const startIndex = startIndices[i];
    const endIndex = startIndices[i + 1];
    const path = [];

    for (let j = startIndex; j < endIndex; j += 1) {
      const x = xs ? xs[j] : coordinates[j * 2];
      const y = ys ? ys[j] : coordinates[j * 2 + 1];
      path.push([a * x + b * y + c, d * x + e * y + f]);
    }

    paths.push(path);
  }

  return paths;
};
