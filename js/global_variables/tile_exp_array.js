import { get_arrow_table } from "../read_parquet/get_arrow_table"
import { options } from '../global_variables/fetch_options.js'
import { tile_names_array } from "../global_variables/tile_names_array.js"
import { tile_name_to_index_map } from "../global_variables/tile_names_array.js"
import { meta_gene } from "../global_variables/meta_gene.js"

export let tile_exp_array

export const update_tile_exp_array = async (base_url, inst_gene) => {

    var exp_table = await get_arrow_table(base_url + 'tbg/' + inst_gene + '.parquet', options.fetch)
    let tile_names = exp_table.getChild('__index_level_0__').toArray()
    let tile_exp = exp_table.getChild(inst_gene).toArray()

    const new_exp_array = new Array(tile_names_array.length).fill(0)

    tile_names.forEach((name, i) => {
        if (tile_name_to_index_map.has(name)) {
            const index = tile_name_to_index_map.get(name)
            const exp_value = Math.log1p(Number(tile_exp[i]))
            const max_exp = Math.log(Number(meta_gene[inst_gene].max))
            new_exp_array[index] = (exp_value / max_exp) * 255
        }
    })

    tile_exp_array = new_exp_array

}