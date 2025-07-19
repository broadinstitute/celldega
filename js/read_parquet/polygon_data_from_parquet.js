import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';
import { get_polygon_data } from './get_polygon_data';

export const polygon_data_from_parquet = async (bytes) => {

  console.log('polygon_data_from_parquet:')

  const table = await arrayBufferToArrowTable(bytes.buffer);

  console.log('table:', table);

  const polygonData = get_polygon_data(table);

  console.log('checking polygonData:', polygonData);

  if (!polygonData) return null;

  const fields = table.schema.fields.map((f) => f.name);
  const propFields = fields.slice(1); // assume geometry column first
  const properties = {};
  for (const f of propFields) {
    properties[f] = table.getChild(f).toArray();
  }

  return { polygonData, properties };
};
