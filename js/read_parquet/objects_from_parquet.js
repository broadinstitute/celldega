import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

/**
 * Converts a Parquet-encoded ArrayBuffer into an object using the specified key field.
 *
 * @param {ArrayBuffer} bytes - The Parquet bytes.
 * @param {string} keyField - The name of the field to use as the key.
 * @returns {Promise<{ result: Object, attr: string[] }>}
 */
export const objects_from_parquet = async (bytes, keyField = '__index_level_0__') => {
  const table = await arrayBufferToArrowTable(bytes.buffer);
  const fields = table.schema.fields.map((f) => f.name);

  if (fields.length < 2) return {};

  if (!fields.includes(keyField)) {
    throw new Error(`Key field "${keyField}" not found in Parquet fields: ${fields.join(', ')}`);
  }


  const keyCol = table.getChild(keyField).toArray();
  const valueFields = fields.filter((f) => f !== keyField);
  const valueCols = valueFields.map((f) => table.getChild(f).toArray());

  const result = {};
  for (let i = 0; i < table.numRows; i++) {
    const key = String(keyCol[i]);
    result[key] = valueCols.map((col) => col[i]);
  }

  console.log('fields', fields);
  console.log('keyField', keyField);
  console.log('valueFields', valueFields);

  return { result, attr: valueFields };
};
