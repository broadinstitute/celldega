const CELL_INDEX_FIELDS = [
  'cell_id',
  '__index_level_0__',
  'cell_name',
  'barcode',
  'barcodes',
  'index',
];

const FALLBACK_NON_EXPRESSION_FIELDS = new Set(['gene']);

const getFieldNames = (table) =>
  table?.schema?.fields?.map((field) => field.name) || [];

const getFirstExistingField = (fields, candidates) =>
  candidates.find((field) => fields.includes(field));

export const getGeneExpressionColumns = (table, geneName) => {
  const fields = getFieldNames(table);
  if (fields.length === 0) {
    return { cell_names: [], cell_exp: [] };
  }

  const cellField = getFirstExistingField(fields, CELL_INDEX_FIELDS);
  const expressionField =
    getFirstExistingField(fields, [geneName, 'expression']) ||
    fields.find(
      (field) =>
        !CELL_INDEX_FIELDS.includes(field) &&
        !FALLBACK_NON_EXPRESSION_FIELDS.has(field)
    );

  if (!cellField || !expressionField) {
    return { cell_names: [], cell_exp: [] };
  }

  return {
    cell_names: table.getChild(cellField)?.toArray() || [],
    cell_exp: table.getChild(expressionField)?.toArray() || [],
    cellField,
    expressionField,
  };
};
