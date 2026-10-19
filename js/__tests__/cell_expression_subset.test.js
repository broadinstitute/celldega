/* global require */

const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(
    path.join(__dirname, '../global_variables/cell_exp_array.js'),
    'utf8'
  )
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export (const |function )/gm, '$1');
const updateExpression = new Function(`
  const options = { fetch: {} };
  const get_arrow_table = async () => ({});
  const getGeneExpressionColumns = () => ({
    cell_names: ['a', 'b', 'c'], cell_exp: [10, 10, 10]
  });
  ${source}
  return update_cell_exp_array;
`)();

describe('gene expression respects the AnnData cell subset', () => {
  test.each([
    [new Set(['b']), [0, 255, 0]],
    [new Set(), [0, 0, 0]],
    [null, [255, 255, 255]],
  ])(
    'restricts expression for metadata selection %s',
    async (allowed, expected) => {
      const cats = {
        cell_names_array: ['a', 'b', 'c'],
        cell_name_to_index_map: new Map([
          ['a', 0],
          ['b', 1],
          ['c', 2],
        ]),
        cell_exp_array: new Uint8Array([255, 255, 255]),
        meta_cell_id_set: allowed,
      };
      await updateExpression(
        cats,
        { meta_gene: { GENE: { max: 10 } } },
        '/data',
        'GENE',
        'default',
        false
      );
      expect(Array.from(cats.cell_exp_array)).toEqual(expected);
    }
  );
});
