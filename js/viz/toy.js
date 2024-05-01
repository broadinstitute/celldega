import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { options, set_options } from '../global_variables/fetch_options.js';
import { update_views } from '../deck-gl/views.js';
import { set_initial_view_state } from "../deck-gl/initial_view_state.js";
import { hexToRgb } from '../utils/hexToRgb.js'

import { deck, set_deck } from '../deck-gl/toy_deck.js'
import { update_layers } from "../deck-gl/toy_layers.js";
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";  

import { update_tile_scatter_data } from "../global_variables/tile_scatter_data.js";
import { update_tile_cats_array } from "../global_variables/tile_cats_array.js";


export const toy = async ( root, base_url ) => {

    set_options('')

    const tile_url = base_url + 'tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)
    update_tile_scatter_data(get_scatter_data(tile_arrow_table))
    update_tile_cats_array(tile_arrow_table.getChild("cluster").toArray())

    let color_dict = {}

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
        color_dict[String(geneName)] = hexToRgb(colors[index]);
    });

    update_square_scatter_layer(color_dict)

    const new_layers = [square_scatter_layer]

    await update_layers(new_layers)

    const ini_x = 500
    const ini_y = 500
    const ini_z = 0
    const ini_zoom = 0

    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)    
    update_views()

    set_deck(root)

    return () => deck.finalize();  

}