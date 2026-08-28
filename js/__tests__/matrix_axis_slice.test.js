/* global require */

describe('matrix axis slice helpers', () => {
  let buildCellSlice;
  let buildColAxisSlice;
  let buildRowAxisSlice;
  let emitMatrixSliceRequest;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../matrix/matrix_axis_slice.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ')
      .replace(/^export function /gm, 'function ');

    const code = `${source}\nmodule.exports = { buildCellSlice, buildColAxisSlice, buildRowAxisSlice, emitMatrixSliceRequest };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({
      buildCellSlice,
      buildColAxisSlice,
      buildRowAxisSlice,
      emitMatrixSliceRequest,
    } = module.exports);
  });

  const make_viz_state = () => ({
    row_nodes: [
      { name: 'row-a' },
      { name: 'row-b' },
      { name: 'row-c' },
      { name: 'row-d' },
    ],
    col_nodes: [
      { name: 'col-a' },
      { name: 'col-b' },
      { name: 'col-c' },
      { name: 'col-d' },
      { name: 'col-e' },
    ],
    mat: {
      net_mat: [
        [0, 5, 2, 9, -1],
        [4, 0, 7, 1, 3],
        [8, 6, 0, 2, 5],
        [1, 10, 3, 0, 4],
      ],
    },
  });

  test('row slices return only the requested top entries', () => {
    const slice = buildRowAxisSlice(make_viz_state(), 0, 2);

    expect(slice.primary_name).toBe('row-a');
    expect(slice.entries).toEqual([
      { row: 0, col: 3, counterpart_name: 'col-d', value: 9 },
      { row: 0, col: 1, counterpart_name: 'col-b', value: 5 },
    ]);
  });

  test('column slices return only the requested top entries', () => {
    const slice = buildColAxisSlice(make_viz_state(), 1, 2);

    expect(slice.primary_name).toBe('col-b');
    expect(slice.entries).toEqual([
      { row: 3, col: 1, counterpart_name: 'row-d', value: 10 },
      { row: 2, col: 1, counterpart_name: 'row-c', value: 6 },
    ]);
  });

  test('negative max_entries keeps all nonzero entries below the safety cap', () => {
    const slice = buildRowAxisSlice(make_viz_state(), 0, -1);

    expect(slice.entries.map((entry) => entry.value)).toEqual([9, 5, 2, -1]);
  });

  test('default slice requests clear then publish a new request id', () => {
    const model = {
      store: {},
      set(key, value) {
        this.store[key] = value;
      },
      save_changes: jest.fn(),
    };

    const req_id = emitMatrixSliceRequest(model, 'row', { index: 1 });

    expect(req_id).toBe(model.store.matrix_slice_request.req_id);
    expect(model.store.matrix_slice_request).toMatchObject({
      op: 'row',
      index: 1,
    });
    expect(model.save_changes).toHaveBeenCalledTimes(1);
  });

  test('cell slices are small direct payloads', () => {
    expect(buildCellSlice(1, 2, 7)).toEqual({
      slice_kind: 'cell',
      matrix_convention:
        'net_mat[row][col] is the matrix entry at row index (row entity) and column index (col entity)',
      row_index: 1,
      col_index: 2,
      value: 7,
    });
  });
});
