import { get_arrow_table } from '../read_parquet/get_arrow_table'
import { options } from '../global_variables/fetch_options.js'

export const update_cell_exp_array = async (cats, genes, base_url, inst_gene) => {

    var file_path = base_url + '/cbg/' + inst_gene + '.parquet'
    var exp_table = await get_arrow_table(file_path, options.fetch)
    let cell_names = exp_table.getChild('__index_level_0__').toArray()
    let cell_exp = exp_table.getChild(inst_gene).toArray()

    const new_exp_array = new Array(cats.cell_names_array.length).fill(0)

    cell_names.forEach((name, i) => {
        if (cats.cell_name_to_index_map.has(name)) {
            const index = cats.cell_name_to_index_map.get(name);
            const exp_value = Number(cell_exp[i]);

            const max_exp = Number(genes.meta_gene[inst_gene].max);

            // Apply logarithmic transformation
            const log_exp_value = Math.log1p(exp_value); // log1p(x) = log(1 + x)

            // Scale to 0-255 range using the log of the max expression value
            const log_max_exp = Math.log1p(max_exp); // log1p(x) = log(1 + x)
            new_exp_array[index] = (log_exp_value / log_max_exp) * 255;
        } else {
            console.log('Cell name not found in cell_name_to_index_map');
        }
    });

    cats.cell_exp_array = new_exp_array

}