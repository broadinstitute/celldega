import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

function extractColumnsFromTable(table) {
  const cols = {};
  table.schema.fields.forEach((f) => {
    cols[f.name] = table.getChild(f.name).toArray();
  });
  return cols;
}

function tableToObjects(table) {
  const cols = extractColumnsFromTable(table);
  const rows = [];
  for (let i = 0; i < table.numRows; i++) {
    const obj = {};
    table.schema.fields.forEach((f) => {
      obj[f.name] = cols[f.name][i];
    });
    rows.push(obj);
  }
  return rows;
}

function tableToMatrix(table) {
  const colNames = table.schema.fields.map((f) => f.name);
  const cols = colNames.map((n) => table.getChild(n).toArray());
  const mat = [];
  for (let r = 0; r < table.numRows; r++) {
    const row = cols.map((c) => c[r]);
    mat.push(Array.from(row));
  }
  return mat;
}

export const networkFromParquet = async (
  meta,
  matBytes,
  rowNodesBytes,
  colNodesBytes,
  rowLinkBytes,
  colLinkBytes
) => {
  const matTable = await arrayBufferToArrowTable(matBytes.buffer);
  const rowNodesTable = await arrayBufferToArrowTable(rowNodesBytes.buffer);
  const colNodesTable = await arrayBufferToArrowTable(colNodesBytes.buffer);
  const rowLinkTable = await arrayBufferToArrowTable(rowLinkBytes.buffer);
  const colLinkTable = await arrayBufferToArrowTable(colLinkBytes.buffer);

  const network = { ...meta };
  network.mat = tableToMatrix(matTable);
  network.row_nodes = tableToObjects(rowNodesTable);
  network.col_nodes = tableToObjects(colNodesTable);
  network.linkage = {
    row: tableToMatrix(rowLinkTable),
    col: tableToMatrix(colLinkTable),
  };

  return network;
};