import { ScatterplotLayer } from 'deck.gl'
import { get_arrow_table } from "../read_parquet/get_arrow_table.js"
import { get_scatter_data } from "../read_parquet/get_scatter_data.js"
import { set_gene_color_dict } from '../global_variables/gene_color_dict.js'
import { set_cell_names_array, set_cell_name_to_index_map } from '../global_variables/cell_names_array.js'
import { options } from '../global_variables/fetch_options.js'
import { cell_cats, set_cell_cats, set_dict_cell_cats, update_selected_cats, selected_cats } from '../global_variables/cat.js'
import { Table } from 'apache-arrow';
import { get_cell_color } from './cell_color.js'
import { layers_ist, update_layers_ist } from './layers_ist.js'
import { deck_ist } from './deck_ist.js'

const get_column_names = (arrowTable) => {

    const columns_to_drop = ['name', 'geometry', '__index_level_0__']

    if (!arrowTable || !(arrowTable instanceof Table)) {
        console.error("Invalid Arrow table")
        return []
    }

    let column_names = []
    for (const field of arrowTable.schema.fields) {
        column_names.push(field.name)
    }

    column_names = column_names.filter(column => !columns_to_drop.includes(column))

    return column_names
}

export let cell_layer = new ScatterplotLayer({
    id: 'cell-layer',
    radiusMinPixels: 1,
    getRadius: 5.0,
    pickable: true,
    getColor: get_cell_color,
})

const cell_layer_onclick = info => {

    // const inst_name = cell_names_array[info.index]
    const inst_cat = cell_cats[info.index]

    update_selected_cats([inst_cat])
    update_cell_layer_id(selected_cats.join('-'))
    update_layers_ist()

    deck_ist.setProps({layers: layers_ist})

}

export const set_cell_layer = async (base_url) => {

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    const column_names = get_column_names(cell_arrow_table)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_gene_color_dict(base_url)

    set_cell_names_array(cell_arrow_table)
    set_cell_name_to_index_map()

    // setting a single cell category for now
    set_cell_cats(cell_arrow_table, column_names[0])
    set_dict_cell_cats()

    cell_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...cell_layer.props,
        data: cell_scatter_data,
        onClick: cell_layer_onclick,
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

    cell_layer = cell_layer.clone({
        id: 'cell-layer-' + new_cat,
    });
}