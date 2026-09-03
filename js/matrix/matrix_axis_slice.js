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
 * Shared core for the row/col axis slices: rank the counterpart axis of
 * `index` by value (non-zero entries only), keeping the top `maxEntries`.
 *
 * @param {'row'|'col'} axis  Primary axis `index` refers to.
 * @param {object} viz_state
 * @param {number} index  Primary-axis matrix index.
 * @param {number} [maxEntries]  Default {@link MAX_ENTRIES}. Use `< 0` for all entries (capped by {@link UNBOUNDED_AXIS_CAP}).
 * @param {(counterpartIndex: number) => boolean} [counterpartFilter]  Optional
 *   predicate on counterpart matrix indices (e.g. crop visibility); entries
 *   failing it are skipped before top-N ranking.
 * @returns {object|null}
 */
const buildAxisSlice = (
  axis,
  viz_state,
  index,
  maxEntries,
  counterpartFilter
) => {
  const net = viz_state?.mat?.net_mat;
  const rowNodes = viz_state?.row_nodes;
  const colNodes = viz_state?.col_nodes;
  if (
    !Array.isArray(net) ||
    !Array.isArray(rowNodes) ||
    !Array.isArray(colNodes) ||
    index == null ||
    Number.isNaN(Number(index))
  ) {
    return null;
  }

  const is_row = axis === 'row';
  const idx = Number(index);
  if (idx < 0 || idx >= (is_row ? net.length : colNodes.length)) return null;
  if (is_row && !Array.isArray(net[idx])) return null;

  const counterpart_nodes = is_row ? colNodes : rowNodes;
  const counterpart_count = is_row ? net[idx].length : net.length;
  const value_at = is_row
    ? (i) => net[idx][i]
    : (i) => {
        const row = net[i];
        return Array.isArray(row) && idx < row.length ? row[idx] : null;
      };

  const cap = resolve_entry_cap(maxEntries);
  const entries = [];
  for (let i = 0; i < counterpart_count; i++) {
    if (counterpartFilter && !counterpartFilter(i)) continue;
    const val = Number(value_at(i));
    if (!Number.isFinite(val) || val === 0) continue;
    const node = counterpart_nodes[i];
    if (!node) continue;
    push_top_entry(entries, cap, {
      row: is_row ? idx : i,
      col: is_row ? i : idx,
      counterpart_name: node.name,
      value: val,
    });
  }

  const primary_node = (is_row ? rowNodes : colNodes)[idx];
  return {
    slice_kind: is_row ? 'row_axis' : 'col_axis',
    matrix_convention: MATRIX_NET_CONVENTION,
    primary_index: idx,
    primary_name: primary_node ? primary_node.name : null,
    entries: sort_entries_desc(entries),
  };
};

/**
 * @param {object} viz_state
 * @param {number} rowIndex
 * @param {number} [maxEntries]  Default {@link MAX_ENTRIES}. Use `< 0` for all entries (capped by {@link UNBOUNDED_AXIS_CAP}).
 * @param {(colIndex: number) => boolean} [counterpartFilter]
 * @returns {object|null}
 */
export function buildRowAxisSlice(
  viz_state,
  rowIndex,
  maxEntries,
  counterpartFilter
) {
  return buildAxisSlice(
    'row',
    viz_state,
    rowIndex,
    maxEntries,
    counterpartFilter
  );
}

/**
 * @param {object} viz_state
 * @param {number} colIndex
 * @param {number} [maxEntries]  Default {@link MAX_ENTRIES}. Use `< 0` for all entries (capped by {@link UNBOUNDED_AXIS_CAP}).
 * @param {(rowIndex: number) => boolean} [counterpartFilter]
 * @returns {object|null}
 */
export function buildColAxisSlice(
  viz_state,
  colIndex,
  maxEntries,
  counterpartFilter
) {
  return buildAxisSlice(
    'col',
    viz_state,
    colIndex,
    maxEntries,
    counterpartFilter
  );
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
