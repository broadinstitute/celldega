export const extractPolygonPaths = (data) => {
  const paths = [];
  const { startIndices, attributes } = data;
  const coordinates = attributes.getPolygon.value;
  const numPolygons = startIndices.length - 1;

   for (let i = 0; i < numPolygons; ++i) {
      // Multiply by 2 because each coordinate is a pair of values (x, y)
      const startIndex = startIndices[i] * 2;
      // The next start index marks the end of the current polygon
      const endIndex = startIndices[i + 1] * 2;
      const path = [];

      for (let j = startIndex; j < endIndex; j += 2) {
         const x = coordinates[j];
         const y = coordinates[j + 1];
         path.push([x, y]);
      }

      paths.push(path);
   }

   return paths;
}