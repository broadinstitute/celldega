import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';

function processExpression(exp_value, max_exp) {
  const log_exp_value = Math.log1p(exp_value);
  const log_max_exp = Math.log1p(max_exp);
  return (log_exp_value / log_max_exp) * 255;
}

export const update_cell_exp_array = async (
  cats,
  genes,
  base_url,
  inst_gene,
  version,
  vector_name_integer,
  aws
) => {

  console.log('------------------------------------------------------')
  console.log('in update_cell_exp_array function')

  let file_path;
  if (version === 'default') {
    file_path = `${base_url}/cbg/${inst_gene}.parquet`;
  } else {
    file_path = `${base_url}/cbg_${version}/${inst_gene}.parquet`;
  }

  const exp_table = await get_arrow_table(file_path, options.fetch, aws);
  console.log('get cell_names')
  const cell_names = exp_table.getChild('__index_level_0__').toArray();
  console.log('get cell_exp')
  const cell_exp = exp_table.getChild(inst_gene).toArray();

  const new_exp_array = new Array(cats.cell_names_array.length).fill(0);

  // Use Sets to track missing names (automatically keeps them unique)
  const missingCellNames1 = new Set(); // For cell_name_to_index_map
  const missingCellNames2 = new Set(); // For nameMapping_inv

  console.log('Updating cell_exp_array for gene:', inst_gene);
  cell_names.forEach((name, i) => {
    name = String(name);
    const exp_value = Number(cell_exp[i]);
    const max_exp = Number(genes.meta_gene[inst_gene].max);

    if (!vector_name_integer) {
      if (cats.cell_name_to_index_map.has(name)) {
        const index = cats.cell_name_to_index_map.get(name);
        new_exp_array[index] = processExpression(exp_value, max_exp);
      } else {
        missingCellNames1.add(name);
      }
    } else {
      if (name in cats.nameMapping_inv) {
        new_exp_array[name] = processExpression(exp_value, max_exp);
      } else {
        missingCellNames2.add(name);
      }
    }
  });

  console.log('done updating cell_exp_array for gene:', inst_gene);

  // Log missing names (if any) after processing all cells
  if (missingCellNames1.size > 0) {
    // console.log(`Cell names not found in cell_name_to_index_map (${missingCellNames1.size} unique names):`,
    //             Array.from(missingCellNames1).slice(0, 5),
    //             missingCellNames1.size > 5 ? '...' : '');
  }
  if (missingCellNames2.size > 0) {
    // console.log(`Cell names not found in cats.nameMapping_inv (${missingCellNames2.size} unique names):`,
    //             Array.from(missingCellNames2).slice(0, 5),
    //             missingCellNames2.size > 5 ? '...' : '');
  }

  cats.cell_exp_array = new_exp_array;

  console.log('end of update_cell_exp_array function')
  console.log('------------------------------------------------------')
};
