export const getTableFieldNames = (table) =>
  table?.schema?.fields?.map((field) => field.name) || [];

const unique = (values) => [...new Set(values.filter(Boolean))];

export const getTableColumn = (table, candidateNames) => {
  const names = Array.isArray(candidateNames)
    ? candidateNames
    : [candidateNames];

  for (const name of unique(names)) {
    const column = table?.getChild?.(name);
    if (column) {
      return {
        name,
        values: Array.from(column.toArray()),
      };
    }
  }

  return { name: null, values: [] };
};

export const getTableColumnArray = (table, candidateNames) =>
  getTableColumn(table, candidateNames).values;

const getMetadataValue = (metadata, key) => {
  if (!metadata) {
    return null;
  }

  if (typeof metadata.get === 'function') {
    return metadata.has?.(key) ? metadata.get(key) : null;
  }

  return Object.prototype.hasOwnProperty.call(metadata, key)
    ? metadata[key]
    : null;
};

export const getPandasMetadata = (table) => {
  const raw = getMetadataValue(table?.schema?.metadata, 'pandas');
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(typeof raw === 'string' ? raw : String(raw));
  } catch {
    return null;
  }
};

const getPandasRangeIndex = (table) => {
  const pandas = getPandasMetadata(table);
  const rangeIndex = pandas?.index_columns?.find?.(
    (indexColumn) =>
      typeof indexColumn === 'object' && indexColumn?.kind === 'range'
  );

  if (!rangeIndex) {
    return null;
  }

  const start = Number(rangeIndex.start ?? 0);
  const step = Number(rangeIndex.step ?? 1);

  return {
    start: Number.isFinite(start) ? start : 0,
    step: Number.isFinite(step) && step !== 0 ? step : 1,
  };
};

export const getFallbackRowKeyArray = (table) => {
  const rowCount = table?.numRows || 0;
  const rangeIndex = getPandasRangeIndex(table);
  const start = rangeIndex?.start ?? 0;
  const step = rangeIndex?.step ?? 1;

  return Array.from({ length: rowCount }, (_, index) =>
    String(start + index * step)
  );
};

export const getRowKeyArray = (
  table,
  candidateNames = ['__index_level_0__'],
  { fallbackToRangeIndex = true } = {}
) => {
  const explicitKeyColumn = getTableColumn(table, candidateNames);
  if (explicitKeyColumn.values.length > 0) {
    return explicitKeyColumn.values.map((value) => String(value));
  }

  return fallbackToRangeIndex ? getFallbackRowKeyArray(table) : [];
};

export const getAlignedColumnArray = (
  table,
  valueColumnName,
  targetKeys = [],
  rowKeyColumnNames = ['name', 'cell_id', '__index_level_0__']
) => {
  const values = getTableColumnArray(table, valueColumnName);
  const explicitKeyColumn = getTableColumn(table, rowKeyColumnNames);

  if (
    explicitKeyColumn.values.length === values.length &&
    values.length > 0 &&
    targetKeys.length > 0
  ) {
    const lookup = new Map();
    explicitKeyColumn.values.forEach((key, index) => {
      lookup.set(String(key), values[index]);
    });

    if (targetKeys.every((key) => lookup.has(String(key)))) {
      return targetKeys.map((key) => lookup.get(String(key)));
    }
  }

  return values;
};
