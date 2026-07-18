import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';
import { getRowKeyArray, getTableColumn } from './table_accessors';

/**
 * Converts a Parquet-encoded ArrayBuffer into an object using the specified key field.
 *
 * @param {ArrayBuffer} bytes - The Parquet bytes.
 * @param {string} keyField - The name of the field to use as the key.
 * @returns {Promise<{ result: Object, attr: string[] }>}
 */
export const objects_from_parquet = async (
  bytes,
  keyField = '__index_level_0__'
) => {
  const table = await arrayBufferToArrowTable(bytes.buffer);
  const fields = table.schema.fields.map((f) => f.name);

  if (fields.length < 2) return { result: {}, attr: [] };

  const keyCandidates = [
    keyField,
    '__index_level_0__',
    'index',
    'name',
    'cell_id',
    'cluster',
    'leiden',
  ];
  const keyColumn = getTableColumn(table, keyCandidates);

  const keyCol =
    keyColumn.values.length > 0
      ? keyColumn.values.map((value) => String(value))
      : getRowKeyArray(table, keyCandidates);
  const valueFields = fields.filter((f) => f !== keyColumn.name);
  const valueCols = valueFields.map((f) => table.getChild(f).toArray());

  const result = {};
  for (let i = 0; i < table.numRows; i++) {
    const key = String(keyCol[i]);
    result[key] = valueCols.map((col) => col[i]);
  }

  return { result, attr: valueFields };
};
