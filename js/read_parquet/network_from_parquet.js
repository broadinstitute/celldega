import { arrayBufferToArrowTable } from './arrayBufferToArrowTable';

function tableToObjects(table) {
  const cols = table.schema.fields.map((f) => ({
    name: f.name,
    data: table.getChild(f.name).toArray(),
  }));
  return Array.from({ length: table.numRows }, (_, i) =>
    Object.fromEntries(cols.map((col) => [col.name, col.data[i]]))
  );
}

function tableToMatrix(table) {
  let colNames = table.schema.fields.map((f) => f.name);
  if (colNames[0] === 'row' || colNames[0] === 'index') {
    colNames = colNames.slice(1);
  }
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
  colLinkBytes,
  dotBytes
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

  // Optional secondary matrix (aligned to `mat`) driving dot-plot size encoding.
  if (dotBytes && dotBytes.byteLength > 0) {
    const dotTable = await arrayBufferToArrowTable(dotBytes.buffer);
    network.size_mat = tableToMatrix(dotTable);
  }

  return network;
};
