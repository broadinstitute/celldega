import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { options } from '../global_variables/fetch_options.js';
import { hexToRgb } from '../utils/hexToRgb.js'

export let tile_color_dict = {}

export const set_tile_color_dict = async (base_url) => {

    const df_colors_url = base_url + `/df_colors.parquet`;
    var df_colors = await get_arrow_table(df_colors_url, options.fetch)

    let names = [];
    let colors = [];

    const nameColumn = df_colors.getChild('__index_level_0__');
    const colorColumn = df_colors.getChild('color');

    if (nameColumn && colorColumn) {
        names = nameColumn.toArray();
        colors = colorColumn.toArray();
    }

    names.forEach((geneName, index) => {
        tile_color_dict[String(geneName)] = hexToRgb(colors[index]);
    });

}