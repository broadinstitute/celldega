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

/**
 * Load a Clustergram network from DegaFiles.
 *
 * @param {string} base_url - Base URL for the DegaFiles directory
 * @param {string} name - Name of the Clustergram (subdirectory under cgm/)
 * @param {object} [options] - Optional fetch options (e.g., headers for authentication)
 * @returns {Promise<object>} - Network object ready for matrix_viz
 */
export const networkFromDegaFiles = async (base_url, name = 'default', options = {}) => {
  const cgm_url = `${base_url}/cgm/${name}`;

  // Fetch all files in parallel
  const [metaRes, matRes, rowNodesRes, colNodesRes, rowLinkRes, colLinkRes] =
    await Promise.all([
      fetch(`${cgm_url}/meta.json`, options),
      fetch(`${cgm_url}/mat.parquet`, options),
      fetch(`${cgm_url}/row_nodes.parquet`, options),
      fetch(`${cgm_url}/col_nodes.parquet`, options),
      fetch(`${cgm_url}/row_linkage.parquet`, options),
      fetch(`${cgm_url}/col_linkage.parquet`, options),
    ]);

  // Check for errors
  if (!metaRes.ok) {
    throw new Error(`Failed to load meta.json: ${metaRes.status}`);
  }

  // Parse metadata
  const meta = await metaRes.json();

  // Get array buffers for parquet files
  const [matBytes, rowNodesBytes, colNodesBytes, rowLinkBytes, colLinkBytes] =
    await Promise.all([
      matRes.arrayBuffer(),
      rowNodesRes.arrayBuffer(),
      colNodesRes.arrayBuffer(),
      rowLinkRes.arrayBuffer(),
      colLinkRes.arrayBuffer(),
    ]);

  // Convert to Arrow tables
  const matTable = await arrayBufferToArrowTable(matBytes);
  const rowNodesTable = await arrayBufferToArrowTable(rowNodesBytes);
  const colNodesTable = await arrayBufferToArrowTable(colNodesBytes);
  const rowLinkTable = await arrayBufferToArrowTable(rowLinkBytes);
  const colLinkTable = await arrayBufferToArrowTable(colLinkBytes);

  // Build network object
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
