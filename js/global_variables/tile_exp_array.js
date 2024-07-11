import { get_arrow_table } from "../read_parquet/get_arrow_table"
import { options } from '../global_variables/fetch_options.js'
import { tile_cats_array } from "../global_variables/tile_cats_array.js"
import { tile_names_array } from "../global_variables/tile_names_array.js"
import { meta_gene } from "../global_variables/meta_gene.js"

// import { get_new_tile_exp_array } from "../global_variables/tile_scatter_data.js"

export let tile_exp_array

export const update_tile_exp_array = async (base_url, inst_gene) => {

    var trx_table = await get_arrow_table(base_url + 'tbg/' + inst_gene + '.parquet', options.fetch)
    let trx_names = trx_table.getChild('__index_level_0__').toArray()
    let trx_exp = trx_table.getChild(inst_gene).toArray()

    const name_to_index_map = new Map()
    tile_names_array.forEach((name, index) => {
        name_to_index_map.set(name, index)
    })

    const new_tile_exp_array = new Array(tile_cats_array.length).fill(0)

    trx_names.forEach((name, i) => {
        if (name_to_index_map.has(name)) {
            const index = name_to_index_map.get(name)
            const exp_value = Number(trx_exp[i])
            const max_exp = Number(meta_gene[inst_gene].max)
            new_tile_exp_array[index] = (exp_value / max_exp) * 255
        }
    })

    tile_exp_array = new_tile_exp_array
}