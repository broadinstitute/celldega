import { global_base_url } from "./global_base_url.js";
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { options } from './fetch_options.js';
import { hexToRgb } from '../utils/hexToRgb.js'

export let color_dict_cluster = {}

export let cluster_counts = []

export const set_cluster_metadata = async  () => {

    // will improve this file naming later
    const meta_cell_url = global_base_url + `/cell_clusters/meta_cluster.parquet`

    var meta_cell_arrow_table = await get_arrow_table(meta_cell_url, options.fetch)

    let cluster_names = []
    let colors = []
    let counts = []

    const cluster_name_column = meta_cell_arrow_table.getChild('__index_level_0__')
    const color_column = meta_cell_arrow_table.getChild('color')
    const counts_column = meta_cell_arrow_table.getChild('count')

    let column_names = []
    for (const field of meta_cell_arrow_table.schema.fields) {
        column_names.push(field.name)
    }

    if (cluster_name_column && color_column) {
        cluster_names = cluster_name_column.toArray()
        colors = color_column.toArray()
        counts = counts_column.toArray()
    }

    cluster_names.forEach((cluster_name, index) => {
        color_dict_cluster[cluster_name] = hexToRgb(colors[index])

        cluster_counts.push({
            name: cluster_name,
            value: Number(counts[index])
        })

    })


    cluster_counts.sort((a, b) => b.value - a.value)

}