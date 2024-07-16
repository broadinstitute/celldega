import { ScatterplotLayer } from 'deck.gl'
import { get_arrow_table } from "../read_parquet/get_arrow_table.js"
import { get_scatter_data } from "../read_parquet/get_scatter_data.js"
import { set_color_dict } from '../global_variables/color_dict.js'
import { cell_names_array, set_cell_names_array, set_cell_name_to_index_map } from '../global_variables/cell_names_array.js'
import { options } from '../global_variables/fetch_options.js'
import { cat } from '../global_variables/cat.js'
import { cell_exp_array } from '../global_variables/cell_exp_array.js'

// transparent to red
const cell_layer_color = (i, d) => {

    if (cat === 'cluster') {
        // const inst_cat = tile_cats_array[d.index];
        // const opacity = (selected_cats.length === 0 || selected_cats.includes(inst_cat)) ? 255 : 25;
        // return [...color_dict[inst_cat], opacity];

        return [0, 0, 255, 255]
    } else {

        const inst_exp = cell_exp_array[d.index]

        return [255, 0, 0, inst_exp]

    }
}

export let cell_layer = new ScatterplotLayer({
    id: 'cell-layer',
    radiusMinPixels: 1.25,
    getRadius: 5.0,
    pickable: true,
    getColor: cell_layer_color,
})


export const update_cell_layer = async (base_url) => {

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_color_dict(base_url)

    set_cell_names_array(cell_arrow_table)
    set_cell_name_to_index_map()

    cell_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...cell_layer.props,
        data: cell_scatter_data,
        onClick: info => {
            console.log('click!!')
            console.log(info.index)
            console.log(cell_names_array[info.index])
        },
    });
}

export const toggle_cell_layer_visibility = (visible) => {
    cell_layer = cell_layer.clone({
        visible: visible,
    });
}

export const update_cell_layer_radius = (radius) => {
    cell_layer = cell_layer.clone({
        getRadius: radius,
    });
}

export const update_cell_layer_id = (new_cat) => {

    console.log('update cell layer id')
    cell_layer = cell_layer.clone({
        id: 'cell-layer-' + new_cat,
    });
}