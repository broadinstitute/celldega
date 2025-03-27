import { get_arrow_table } from '../read_parquet/get_arrow_table'
import { options } from '../global_variables/fetch_options.js'

function processExpression(exp_value, max_exp) {
    const log_exp_value = Math.log1p(exp_value);
    const log_max_exp = Math.log1p(max_exp);
    return (log_exp_value / log_max_exp) * 255;
}


export const update_cell_exp_array = async (cats, genes, base_url, inst_gene, version, vector_name_integer) => {

    let file_path;
    if (version === 'default'){
        file_path = base_url + '/cbg/' + inst_gene + '.parquet';
    } else {
        file_path = base_url + '/cbg_' + version + '/' + inst_gene + '.parquet';
    }

    //var file_path = base_url + '/cbg/' + inst_gene + '.parquet'
    var exp_table = await get_arrow_table(file_path, options.fetch)
    let cell_names = exp_table.getChild('__index_level_0__').toArray()
    let cell_exp = exp_table.getChild(inst_gene).toArray()

    const new_exp_array = new Array(cats.cell_names_array.length).fill(0)

    console.log('vector_name_integer:',vector_name_integer)
    
    cell_names.forEach((name, i) => {
        name = String(name);
        const exp_value = Number(cell_exp[i]);
        const max_exp = Number(genes.meta_gene[inst_gene].max);

        if (!vector_name_integer) {
            if (cats.cell_name_to_index_map.has(name)) {
                const index = cats.cell_name_to_index_map.get(name);
                new_exp_array[index] = processExpression(exp_value, max_exp);
            } else {
                console.log('Cell name not found in cell_name_to_index_map');
            }
        } else {
            if (name in cats.nameMapping_inv) {
                new_exp_array[name] = processExpression(exp_value, max_exp);
            } else {
                console.log('Cell name not found in cats.nameMapping_inv');
            }
        }
    });

    cats.cell_exp_array = new_exp_array;
}