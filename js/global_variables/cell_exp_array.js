import { get_arrow_table } from '../read_parquet/get_arrow_table'
import { options } from '../global_variables/fetch_options.js'
import { cell_names_array } from './cell_names_array.js'
import { cell_name_to_index_map } from './cell_names_array.js'

export let cell_exp_array

export const update_cell_exp_array = async (base_url, inst_gene) => {

    var file_path = base_url + '/cbg/' + inst_gene + '.parquet'
    console.log('file_path', file_path)

    var exp_table = await get_arrow_table(file_path, options.fetch)
    let cell_names = exp_table.getChild('__index_level_0__').toArray()
    let cell_exp = exp_table.getChild(inst_gene).toArray()

    console.log('cell_names', cell_names.slice(0, 10))
    console.log('cell_exp', cell_exp.slice(0, 10))

    const new_exp_array = new Array(cell_names_array.length).fill(0)

    cell_names.forEach((name, i) => {
        if (cell_name_to_index_map.has(name)) {
            const index = cell_name_to_index_map.get(name)
            const exp_value = Number(cell_exp[i])
            const max_exp = Number(meta_gene[inst_gene].max)
            new_exp_array[index] = (exp_value / max_exp) * 255
        }
    })

    cell_exp_array = new_exp_array

}