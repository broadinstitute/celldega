import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

// Convert a Parquet-encoded ArrayBuffer to a dictionary mapping the
// first column to the remaining column values. If only two columns
// are present the value will be a single item, otherwise an array.
export const objectsFromParquet = async (bytes) => {
  const table = await arrayBufferToArrowTable(bytes.buffer);
  const fields = table.schema.fields.map((f) => f.name);
  if (fields.length < 2) {
    return {};
  }
  const keyCol = table.getChild(fields[0]).toArray();
  const valueCols = fields.slice(1).map((n) => table.getChild(n).toArray());

  const result = {};
  for (let i = 0; i < table.numRows; i++) {
    if (valueCols.length === 1) {
      result[keyCol[i]] = valueCols[0][i];
    } else {
      result[keyCol[i]] = valueCols.map((col) => col[i]);
    }
  }
  return result;
};
