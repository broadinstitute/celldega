import * as d3 from 'd3'
import { ScatterplotLayer } from 'deck.gl'
import { get_arrow_table } from "../read_parquet/get_arrow_table"
import { get_scatter_data } from "../read_parquet/get_scatter_data"
import { set_color_dict_gene } from '../global_variables/color_dict_gene'
import { set_cell_names_array, set_cell_name_to_index_map } from '../global_variables/cell_names_array'
import { options } from '../global_variables/fetch_options'
import { cell_cats, set_cell_cats, dict_cell_cats, set_dict_cell_cats} from '../global_variables/cat'
import { update_selected_cats, selected_cats, update_cat, reset_cat } from '../global_variables/cat'
import { get_cell_color } from './cell_color'
import { get_layers_list } from './layers_ist'
import { update_path_layer_id } from './path_layer'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { update_selected_genes } from '../global_variables/selected_genes'
import { update_trx_layer_id } from './trx_layer'
import { svg_bar_cluster, bar_container_cluster, svg_bar_gene } from '../ui/bar_plot'
import { gene_search_input } from '../ui/gene_search_input'
import { update_gene_text_box } from '../ui/gene_search'
import { tooltip_cat_cell } from './make_tooltip'

export let cell_scatter_data
export let cell_combo_data

const cell_layer_onclick = async (info, d, deck_ist, layers_obj, viz_state) => {

    // Check if the device is a touch device
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    let inst_cat;

    if (isTouchDevice) {
        // Fallback on the previous method for touch devices
        inst_cat = cell_cats[info.index];
    } else {
        // Use the tooltip category for non-touch devices
        inst_cat = tooltip_cat_cell;
    }

    update_cat('cluster')
    update_selected_cats([inst_cat])
    update_selected_genes([])

    toggle_image_layers_and_ctrls(layers_obj, viz_state, !selected_cats.length > 0)

    const inst_cat_name = selected_cats.join('-')

    // reset gene
    svg_bar_gene
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 1.0)

    svg_bar_cluster.selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', reset_cat ? 1.0 : 0.25)

    if (!reset_cat) {
        const selectedBar = svg_bar_cluster.selectAll("g")
            .filter(function() {
                return d3.select(this).select("text").text() === inst_cat
            })
            .attr('opacity', 1.0)

        if (!selectedBar.empty()) {
            const barPosition = selectedBar.node().getBoundingClientRect().top
            const containerPosition = bar_container_cluster.getBoundingClientRect().top
            const scrollPosition = barPosition - containerPosition + bar_container_cluster.scrollTop

            bar_container_cluster.scrollTo({
                top: scrollPosition,
                behavior: 'smooth'
            })
        }
    } else {
        bar_container_cluster.scrollTo({
            top: 0,
            behavior: 'smooth'
        })
    }

    update_cell_layer_id(layers_obj, inst_cat_name)
    update_path_layer_id(layers_obj, inst_cat_name)
    update_trx_layer_id(layers_obj)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    gene_search_input.value = ''
    update_gene_text_box('')

}

export const ini_cell_layer = async (base_url) => {

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_color_dict_gene(base_url)

    set_cell_names_array(cell_arrow_table)
    set_cell_name_to_index_map()

    // default clustering
    var cluster_arrow_table = await get_arrow_table(base_url + `/cell_clusters/cluster.parquet`, options.fetch)

    // setting a single cell category for now
    set_cell_cats(cluster_arrow_table, 'cluster')
    set_dict_cell_cats()

    // Combine names and positions into a single array of objects
    const new_cell_names_array = cell_arrow_table.getChild("name").toArray()

    // need to save the cell category
    const flatCoordinateArray = cell_scatter_data.attributes.getPosition.value;

    // save cell positions and categories in one place for updating cluster bar plot
    cell_combo_data = new_cell_names_array.map((name, index) => ({
        name: name,
        cat: dict_cell_cats[name],
        x: flatCoordinateArray[index * 2],
        y: flatCoordinateArray[index * 2 + 1]
    }))

    let cell_layer = new ScatterplotLayer({
        id: 'cell-layer',
        radiusMinPixels: 1,
        getRadius: 5.0,
        pickable: true,
        getColor: get_cell_color,
        data: cell_scatter_data,
    })

    return cell_layer

}

export const set_cell_layer_onclick = (deck_ist, layers_obj, viz_state) => {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        onClick: (event, d) => cell_layer_onclick(event, d, deck_ist, layers_obj, viz_state)
    })
}

export const update_cell_combo_data = () => {

    cell_combo_data = cell_combo_data.map((cell) => ({
      ...cell,
      cat: dict_cell_cats[cell.name]
    }))

}

export const new_toggle_cell_layer_visibility = (layers_obj, visible) => {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        visible: visible,
    });
}

export const update_cell_layer_radius = (layers_obj, radius) => {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        getRadius: radius,
    });
}

export const update_cell_layer_id = (layers_obj, new_cat) => {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        id: 'cell-layer-' + new_cat,
    })
}