import { global_base_url } from "./global_base_url.js";
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { options } from './fetch_options.js';
import { hexToRgb } from '../utils/hexToRgb.js'

export let cell_color_dict = {}

export let cluster_counts = {}

export const set_cluster_metadata = async  () => {

    // will improve this file naming later
    const meta_cell_url = global_base_url + `/meta_cluster.parquet`

    var meta_cell_arrow_table = await get_arrow_table(meta_cell_url, options.fetch)

    let cluster_names = []
    let colors = []
    let counts = []

    const cellNameColumn = meta_cell_arrow_table.getChild('__index_level_0__')
    const colorColumn = meta_cell_arrow_table.getChild('color')
    const countsColumn = meta_cell_arrow_table.getChild('count')

    let column_names = []
    for (const field of meta_cell_arrow_table.schema.fields) {
        column_names.push(field.name)
    }

    console.log(column_names)

    console.log(countsColumn)

    if (cellNameColumn && colorColumn) {
        cluster_names = cellNameColumn.toArray()
        colors = colorColumn.toArray()
        counts = countsColumn.toArray()
    }

    console.log('cluster_names', cluster_names.length, cluster_names)
    console.log('colors', colors.length, colors)
    console.log('counts', counts)

    cluster_names.forEach((cellName, index) => {
        cell_color_dict[cellName] = hexToRgb(colors[index])
    })

}