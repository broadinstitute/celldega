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

const resolve_entry_cap = (max_entries) => {
  if (max_entries == null) return MAX_ENTRIES;

  const value = Number(max_entries);
  if (!Number.isFinite(value)) return MAX_ENTRIES;
  if (value < 0) return UNBOUNDED_AXIS_CAP;

  return Math.min(Math.floor(value), UNBOUNDED_AXIS_CAP);
};

const swap = (array, i, j) => {
  const tmp = array[i];
  array[i] = array[j];
  array[j] = tmp;
};

const bubble_up = (heap, index) => {
  let child = index;
  while (child > 0) {
    const parent = Math.floor((child - 1) / 2);
    if (heap[parent].value <= heap[child].value) break;
    swap(heap, parent, child);
    child = parent;
  }
};

const sink_down = (heap, index) => {
  let parent = index;

  while (true) {
    const left = parent * 2 + 1;
    const right = left + 1;
    let smallest = parent;

    if (left < heap.length && heap[left].value < heap[smallest].value) {
      smallest = left;
    }
    if (right < heap.length && heap[right].value < heap[smallest].value) {
      smallest = right;
    }
    if (smallest === parent) break;

    swap(heap, parent, smallest);
    parent = smallest;
  }
};

const push_top_entry = (heap, cap, entry) => {
  if (cap <= 0) return;

  if (heap.length < cap) {
    heap.push(entry);
    bubble_up(heap, heap.length - 1);
    return;
  }

  if (entry.value <= heap[0].value) return;

  heap[0] = entry;
  sink_down(heap, 0);
};

const sort_entries_desc = (entries) =>
  entries.sort((a, b) => b.value - a.value);

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

  const cap = resolve_entry_cap(maxEntries);
  const entries = [];
  for (let c = 0; c < row.length; c++) {
    const val = Number(row[c]);
    if (!Number.isFinite(val) || val === 0) continue;
    const cn = colNodes[c];
    if (!cn) continue;
    push_top_entry(entries, cap, {
      row: r,
      col: c,
      counterpart_name: cn.name,
      value: val,
    });
  }
  const primaryNode = rowNodes[r];
  return {
    slice_kind: 'row_axis',
    matrix_convention: MATRIX_NET_CONVENTION,
    primary_index: r,
    primary_name: primaryNode ? primaryNode.name : null,
    entries: sort_entries_desc(entries),
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

  const cap = resolve_entry_cap(maxEntries);
  const entries = [];
  for (let r = 0; r < net.length; r++) {
    const row = net[r];
    if (!Array.isArray(row) || c >= row.length) continue;
    const val = Number(row[c]);
    if (!Number.isFinite(val) || val === 0) continue;
    const rn = rowNodes[r];
    if (!rn) continue;
    push_top_entry(entries, cap, {
      row: r,
      col: c,
      counterpart_name: rn.name,
      value: val,
    });
  }
  const primaryNode = colNodes[c];
  return {
    slice_kind: 'col_axis',
    matrix_convention: MATRIX_NET_CONVENTION,
    primary_index: c,
    primary_name: primaryNode ? primaryNode.name : null,
    entries: sort_entries_desc(entries),
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
