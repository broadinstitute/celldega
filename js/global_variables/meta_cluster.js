import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { options } from './fetch_options.js';
import { hexToRgb } from '../utils/hexToRgb.js'

export const update_meta_cluster = (cats, new_meta_cluster) => {

    cats.color_dict_cluster = new_meta_cluster.color

    // convert each hexcode color value to rgb
    for (const cluster_name in cats.color_dict_cluster) {
        cats.color_dict_cluster[cluster_name] = hexToRgb(cats.color_dict_cluster[cluster_name])
    }

    var cluster_counts_ini = new_meta_cluster.count

    // convert cluster_counts_ini into an array of objects with values name and value
    cats.cluster_counts = []
    for (const cluster_name in cluster_counts_ini) {
        cats.cluster_counts.push({
            name: cluster_name,
            value: cluster_counts_ini[cluster_name]
        })
    }

    cats.cluster_counts.sort((a, b) => b.value - a.value)

}

export const set_cluster_metadata = async (viz_state) => {

    if (viz_state.cats.has_meta_cluster) {

        // loop through the keys of meta_cluster and assemble a dictionary of colors use a map or something functional
        for (const cluster_name in viz_state.cats.meta_cluster) {
            viz_state.cats.color_dict_cluster[cluster_name] = hexToRgb(viz_state.cats.meta_cluster[cluster_name]['color'])
        }

        // loop through the keys and assembe cluster_counts
        for (const cluster_name in viz_state.cats.meta_cluster) {
            viz_state.cats.cluster_counts.push({
                name: cluster_name,
                value: viz_state.cats.meta_cluster[cluster_name]['count']
            })
        }


    } else {

        // will improve this file naming later
        const meta_cell_url = viz_state.global_base_url + `/cell_clusters/meta_cluster.parquet`

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
            viz_state.cats.color_dict_cluster[cluster_name] = hexToRgb(colors[index])

            viz_state.cats.cluster_counts.push({
                name: cluster_name,
                value: Number(counts[index])
            })

        })
    }

    viz_state.cats.cluster_counts.sort((a, b) => b.value - a.value)

}