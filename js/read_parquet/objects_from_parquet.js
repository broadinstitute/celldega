import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

/**
 * Converts a Parquet-encoded ArrayBuffer into an object using the DataFrame index as key.
 *
 * Works whether the index is named or not (e.g. "__index_level_0__").
 *
 * @param {ArrayBuffer} bytes - The buffer to decode.
 * @returns {Promise<Object>} - Object mapping index → [values] or single value.
 */
export const objects_from_parquet = async (bytes) => {
  const table = await arrayBufferToArrowTable(bytes.buffer);
  const fields = table.schema.fields.map((f) => f.name);

  if (fields.length < 2) return {};

  // Check if the index is explicitly preserved
  const indexField = fields.find((f) =>
    f === '__index_level_0__' || !f.match(/^[a-zA-Z_]/) // conservative fallback
  ) || fields[0];  // fallback to first field if no index column is clearly marked

  const keyCol = table.getChild(indexField).toArray();
  const valueFields = fields.filter((f) => f !== indexField);
  const valueCols = valueFields.map((f) => table.getChild(f).toArray());

  const result = {};
  for (let i = 0; i < table.numRows; i++) {
    const key = String(keyCol[i]);
    result[key] = valueCols.map((col) => col[i]);
  }


  return {result, fields};
};
