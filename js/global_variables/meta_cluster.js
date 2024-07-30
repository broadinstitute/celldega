import { global_base_url } from "./global_base_url.js";
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { options } from './fetch_options.js';
import { hexToRgb } from '../utils/hexToRgb.js'

export let color_dict_cluster = {}

export let cluster_counts = []

export const update_meta_cluster = (new_meta_cluster) => {

    console.log('update_meta_cluster: new_meta_cluster', new_meta_cluster)

    color_dict_cluster = new_meta_cluster.color

    console.log('update_meta_cluster: color_dict_cluster', color_dict_cluster)

    // convert each hexcode color value to rgb
    for (const cluster_name in color_dict_cluster) {
        color_dict_cluster[cluster_name] = hexToRgb(color_dict_cluster[cluster_name])
    }

    var cluster_counts_ini = new_meta_cluster.count
    console.log('counts!!!!!!!!!!!!!!!!!!!!')


    // convert cluster_counts_ini into an array of objects with values name and value
    cluster_counts = []
    for (const cluster_name in cluster_counts_ini) {
        cluster_counts.push({
            name: cluster_name,
            value: cluster_counts_ini[cluster_name]
        })
    }

    cluster_counts.sort((a, b) => b.value - a.value)

    console.log('cluster_counts_ini', cluster_counts_ini)
    console.log('cluster_counts', cluster_counts)
}

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

    // console.log('color_dict_cluster', color_dict_cluster)
    // console.log('cluster_counts', cluster_counts)


    cluster_counts.sort((a, b) => b.value - a.value)

}