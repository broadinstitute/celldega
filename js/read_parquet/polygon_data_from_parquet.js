import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';
import { get_polygon_data } from './get_polygon_data';

export const polygonDataFromParquet = async (bytes) => {
  const table = await arrayBufferToArrowTable(bytes.buffer);
  const polygonData = get_polygon_data(table);
  if (!polygonData) return null;

  const fields = table.schema.fields.map((f) => f.name);
  const propFields = fields.slice(1); // assume geometry column first
  const properties = {};
  for (const f of propFields) {
    properties[f] = table.getChild(f).toArray();
  }

  return { polygonData, properties };
};
