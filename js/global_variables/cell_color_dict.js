import { global_base_url } from "./global_base_url";
import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { options } from './fetch_options.js';
import { hexToRgb } from '../utils/hexToRgb.js'

export let cell_color_dict = {}

export const set_cell_color_dict = async  () => {

    // will improve this file naming later
    const cell_colors_url = global_base_url + `/meta_cluster.parquet`;
    var cell_colors = await get_arrow_table(cell_colors_url, options.fetch)

    let cell_names = [];
    let colors = [];

    const cellNameColumn = cell_colors.getChild('__index_level_0__');
    const colorColumn = cell_colors.getChild('color');

    if (cellNameColumn && colorColumn) {
        cell_names = cellNameColumn.toArray();
        colors = colorColumn.toArray();
    }

    cell_names.forEach((cellName, index) => {
        cell_color_dict[cellName] = hexToRgb(colors[index]);
    })

}