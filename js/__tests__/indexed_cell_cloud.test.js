/* global require */

const fs = require('fs');
const path = require('path');

const source = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const {
  set_indexed_cell_names_array,
  set_cell_names_array,
  set_cell_cats,
  execute_cell_query,
  get_scatter_data,
} = new Function(`
    const options = { fetch: {} };
    const get_arrow_table = async () => { throw new Error('No DegaFiles request expected'); };
    ${source('read_parquet/table_accessors.js')}
    ${source('global_variables/cell_names_array.js')}
    ${source('global_variables/cat.js')}
    ${source('utils/cell_query.js')}
    ${source('read_parquet/get_scatter_data.js')}
    return { set_indexed_cell_names_array, set_cell_names_array, set_cell_cats, execute_cell_query, get_scatter_data };
  `)();
const table = (columns) => ({
  numRows: Object.values(columns)[0]?.length ?? 0,
  getChild: (key) => (key in columns ? { toArray: () => columns[key] } : null),
});

describe('indexed CellCloud identities', () => {
  test('preserves original IDs once and aligns permuted numeric clusters', () => {
    const cats = {};
    set_indexed_cell_names_array(
      cats,
      table({ name: Uint32Array.from([0, 1, 2]) }),
      table({
        name: ['slice_1_barcode_A', 'slice_2_barcode_A', 'slice_2_barcode_B'],
      })
    );
    set_cell_cats(
      cats,
      table({ name: Uint32Array.from([2, 0, 1]), cluster: ['C', 'A', 'B'] }),
      'cluster'
    );
    expect(cats.nameMapping_inv).toBe(cats.cell_names_array);
    expect(cats.cell_names_array).toEqual([
      'slice_1_barcode_A',
      'slice_2_barcode_A',
      'slice_2_barcode_B',
    ]);
    expect(cats.cell_cats).toEqual(['A', 'B', 'C']);
  });

  test('rejects geometry in a different row order and missing identity rows', () => {
    expect(() =>
      set_indexed_cell_names_array(
        {},
        table({ name: [1, 0] }),
        table({ name: ['a', 'b'] })
      )
    ).toThrow(/cell_ids row order/);
    expect(() =>
      set_indexed_cell_names_array(
        {},
        table({ name: [0, 1] }),
        table({ name: ['a'] })
      )
    ).toThrow(/cell_ids row order/);
  });

  test.each([
    [0, 0],
    [0, 2],
    [-1, 1],
    [0.5, 1],
  ])('rejects invalid cluster keys %j', (a, b) => {
    const cats = { cell_ids_are_indexed: true, cell_names_array: ['a', 'b'] };
    expect(() =>
      set_cell_cats(
        cats,
        table({ name: [a, b], cluster: ['A', 'B'] }),
        'cluster'
      )
    ).toThrow(/Invalid or duplicate/);
  });

  test('continues matching legacy string-keyed clusters after an indexed dataset', () => {
    const cats = { cell_ids_are_indexed: true };
    set_cell_names_array(cats, table({ name: ['b', 'a'] }));
    set_cell_cats(
      cats,
      table({ name: ['a', 'b'], cluster: ['A', 'B'] }),
      'cluster'
    );
    expect(cats.cell_ids_are_indexed).toBe(false);
    expect(cats.cell_cats).toEqual(['B', 'A']);
  });

  test('queries clusters and Zarr genes using original cell IDs', async () => {
    const state = {
      cats: {
        inst_cell_attr: 'cluster',
        cell_names_array: ['original-A', 'original-B', 'original-C'],
        nameMapping_inv: ['original-A', 'original-B', 'original-C'],
        cell_cats: ['A', 'B', 'A'],
      },
      vector_name_integer: true,
      seg: { version: 'default' },
      row_group_readers: {
        cbg: {
          readGeneExpression: async () => ({
            cell_names: Int32Array.from([0, 1, 2]),
            cell_exp: Float32Array.from([1, 100, 9]),
          }),
        },
      },
    };
    expect(
      await execute_cell_query(
        { cluster: { attr: 'cluster', value: 'A' }, gene: 'G' },
        state
      )
    ).toEqual(['original-C', 'original-A']);
  });

  test('can decode integer geometry directly into the Float32 GPU buffer', () => {
    const geometry = {
      numRows: 2,
      getChild: () => ({
        getChildAt: () => ({
          data: [{ values: Int32Array.from([1, 2, 3, -1, -2, -3]) }],
        }),
      }),
    };
    const compact = get_scatter_data(geometry, { float32: true });
    const legacy = get_scatter_data(geometry);
    expect(compact.attributes.getPosition.value).toEqual(
      Float32Array.from([1, 2, 3, -1, -2, -3])
    );
    expect(legacy.attributes.getPosition.value).toBeInstanceOf(Float64Array);
    expect(compact.attributes.getPosition.size).toBe(3);
  });
});
