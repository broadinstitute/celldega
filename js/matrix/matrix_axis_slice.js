/**
 * Generic matrix axis slices from `viz_state.mat.net_mat`.
 *
 * Convention: `net_mat[row_index][col_index]` is the scalar at that row/column entity
 * pair (interpretation of row vs col entities is up to the application).
 */

const MAX_ENTRIES = 2000;
/** When `max_entries < 0` (request all), still cap per axis to avoid freezing huge matrices. */
const UNBOUNDED_AXIS_CAP = 500_000;

export const MATRIX_NET_CONVENTION =
  'net_mat[row][col] is the matrix entry at row index (row entity) and column index (col entity)';

/**
 * Ask the widget model to run the front-end slice handler (second step after a click).
 * @param {any} model  ipywidgets Backbone model with get/set/save_changes
 * @param {'row'|'col'|'cell'|'row_col'} op
 * @param {Record<string, unknown>} fields  Optional `max_entries` on `row`/`col`/`row_col`
 *   (`< 0` = all non-zero entries, up to an internal cap; omit = {@link MAX_ENTRIES}).
 * @returns {string|undefined} req_id
 */
export function emitMatrixSliceRequest(model, op, fields) {
  if (!model?.set) return undefined;
  const req_id =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `r${Date.now()}-${Math.random().toString(16).slice(2)}`;
  model.set('matrix_slice_request', {});
  model.set('matrix_slice_request', { req_id, op, ...fields });
  model.save_changes();
  return req_id;
}

/**
 * @param {object} viz_state
 * @param {number} rowIndex
 * @param {number} [maxEntries]  Default {@link MAX_ENTRIES}. Use `< 0` for all entries (capped by {@link UNBOUNDED_AXIS_CAP}).
 * @returns {object|null}
 */
export function buildRowAxisSlice(viz_state, rowIndex, maxEntries) {
  const net = viz_state?.mat?.net_mat;
  const rowNodes = viz_state?.row_nodes;
  const colNodes = viz_state?.col_nodes;
  if (
    !Array.isArray(net) ||
    !Array.isArray(rowNodes) ||
    !Array.isArray(colNodes) ||
    rowIndex == null ||
    Number.isNaN(Number(rowIndex))
  ) {
    return null;
  }
  const r = Number(rowIndex);
  if (r < 0 || r >= net.length) return null;
  const row = net[r];
  if (!Array.isArray(row)) return null;

  const entries = [];
  for (let c = 0; c < row.length; c++) {
    const val = Number(row[c]);
    if (!Number.isFinite(val) || val === 0) continue;
    const cn = colNodes[c];
    if (!cn) continue;
    entries.push({
      row: r,
      col: c,
      counterpart_name: cn.name,
      value: val,
    });
  }
  entries.sort((a, b) => b.value - a.value);
  const cap =
    maxEntries == null
      ? MAX_ENTRIES
      : maxEntries < 0
        ? Math.min(entries.length, UNBOUNDED_AXIS_CAP)
        : Math.min(entries.length, maxEntries, UNBOUNDED_AXIS_CAP);
  const primaryNode = rowNodes[r];
  return {
    slice_kind: 'row_axis',
    matrix_convention: MATRIX_NET_CONVENTION,
    primary_index: r,
    primary_name: primaryNode ? primaryNode.name : null,
    entries: entries.slice(0, cap),
  };
}

/**
 * @param {object} viz_state
 * @param {number} colIndex
 * @param {number} [maxEntries]  Default {@link MAX_ENTRIES}. Use `< 0` for all entries (capped by {@link UNBOUNDED_AXIS_CAP}).
 * @returns {object|null}
 */
export function buildColAxisSlice(viz_state, colIndex, maxEntries) {
  const net = viz_state?.mat?.net_mat;
  const rowNodes = viz_state?.row_nodes;
  const colNodes = viz_state?.col_nodes;
  if (
    !Array.isArray(net) ||
    !Array.isArray(rowNodes) ||
    !Array.isArray(colNodes) ||
    colIndex == null ||
    Number.isNaN(Number(colIndex))
  ) {
    return null;
  }
  const c = Number(colIndex);
  if (c < 0 || c >= colNodes.length) return null;

  const entries = [];
  for (let r = 0; r < net.length; r++) {
    const row = net[r];
    if (!Array.isArray(row) || c >= row.length) continue;
    const val = Number(row[c]);
    if (!Number.isFinite(val) || val === 0) continue;
    const rn = rowNodes[r];
    if (!rn) continue;
    entries.push({
      row: r,
      col: c,
      counterpart_name: rn.name,
      value: val,
    });
  }
  entries.sort((a, b) => b.value - a.value);
  const cap =
    maxEntries == null
      ? MAX_ENTRIES
      : maxEntries < 0
        ? Math.min(entries.length, UNBOUNDED_AXIS_CAP)
        : Math.min(entries.length, maxEntries, UNBOUNDED_AXIS_CAP);
  const primaryNode = colNodes[c];
  return {
    slice_kind: 'col_axis',
    matrix_convention: MATRIX_NET_CONVENTION,
    primary_index: c,
    primary_name: primaryNode ? primaryNode.name : null,
    entries: entries.slice(0, cap),
  };
}

/**
 * @param {number} rowIndex
 * @param {number} colIndex
 * @param {unknown} value
 */
export function buildCellSlice(rowIndex, colIndex, value) {
  return {
    slice_kind: 'cell',
    matrix_convention: MATRIX_NET_CONVENTION,
    row_index: rowIndex,
    col_index: colIndex,
    value,
  };
}

/**
 * One response containing a normal row-axis slice and a normal col-axis slice
 * (e.g. same entity on both axes in a square flow matrix).
 *
 * @param {object} viz_state
 * @param {number} rowIndex
 * @param {number} colIndex
 * @param {number} [maxEntries]  Passed through to both axis builders.
 * @returns {object|null}
 */
export function buildRowColPairSlice(
  viz_state,
  rowIndex,
  colIndex,
  maxEntries
) {
  const rowSlice = buildRowAxisSlice(viz_state, rowIndex, maxEntries);
  const colSlice = buildColAxisSlice(viz_state, colIndex, maxEntries);
  if (!rowSlice && !colSlice) return null;
  return {
    slice_kind: 'row_col',
    matrix_convention: MATRIX_NET_CONVENTION,
    row_axis: rowSlice,
    col_axis: colSlice,
  };
}
