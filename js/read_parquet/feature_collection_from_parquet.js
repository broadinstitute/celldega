import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';
import { get_polygon_data } from './get_polygon_data';
import { extractPolygonPaths } from '../vector_tile/polygons/extractPolygonPaths';

export const feature_collectoin_from_parquet = async (bytes) => {
  const table = await arrayBufferToArrowTable(bytes.buffer);
  const polygonData = get_polygon_data(table);
  if (!polygonData) {
    return { type: 'FeatureCollection', features: [] };
  }
  const paths = extractPolygonPaths(polygonData);
  const fields = table.schema.fields.map((f) => f.name);
  const propFields = fields.slice(1); // assume geometry column first

  const features = [];
  for (let i = 0; i < paths.length; i++) {
    const props = {};
    for (const f of propFields) {
      const col = table.getChild(f);
      props[f] = col ? col.toArray()[i] : null;
    }
    features.push({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [paths[i]] },
      properties: props,
    });
  }

  return { type: 'FeatureCollection', features };
};
