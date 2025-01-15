import * as d3 from 'd3'
import { ScatterplotLayer } from 'deck.gl'
import { get_arrow_table } from "../read_parquet/get_arrow_table"
import { get_scatter_data } from "../read_parquet/get_scatter_data"
import { set_color_dict_gene } from '../global_variables/color_dict_gene'
import { set_cell_names_array, set_cell_name_to_index_map } from '../global_variables/cell_names_array'
import { options } from '../global_variables/fetch_options'
import { set_cell_cats, set_dict_cell_cats} from '../global_variables/cat'
import { update_selected_cats, update_cat } from '../global_variables/cat'
import { get_cell_color } from './cell_color'
import { get_layers_list } from './layers_ist'
import { update_path_layer_id } from './path_layer'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { update_selected_genes } from '../global_variables/selected_genes'
import { update_trx_layer_id } from './trx_layer'
import { update_gene_text_box } from '../ui/gene_search'
import { scale_umap_data } from '../umap/scale_umap_data'

const cell_layer_onclick = async (info, d, deck_ist, layers_obj, viz_state) => {

    // Check if the device is a touch device
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    let inst_cat;

    if (isTouchDevice) {
        // Fallback on the previous method for touch devices
        inst_cat = viz_state.cats.cell_cats[info.index];
    } else {
        // Use the tooltip category for non-touch devices
        inst_cat = viz_state.tooltip_cat_cell;
    }

    update_cat(viz_state.cats, 'cluster')
    update_selected_cats(viz_state.cats, [inst_cat])
    update_selected_genes(viz_state.genes, [])

    toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

    const inst_cat_name = viz_state.cats.selected_cats.join('-')

    // reset gene
    viz_state.genes.svg_bar_gene
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 1.0)

    viz_state.cats.svg_bar_cluster.selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', viz_state.cats.reset_cat ? 1.0 : 0.25)

    if (!viz_state.cats.reset_cat) {
        const selectedBar = viz_state.cats.svg_bar_cluster.selectAll("g")
            .filter(function() {
                return d3.select(this).select("text").text() === inst_cat
            })
            .attr('opacity', 1.0)

        if (!selectedBar.empty()) {
            const barPosition = selectedBar.node().getBoundingClientRect().top
            const containerPosition = viz_state.containers.bar_cluster.getBoundingClientRect().top
            const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_cluster.scrollTop

            viz_state.containers.bar_cluster.scrollTo({
                top: scrollPosition,
                behavior: 'smooth'
            })
        }
    } else {
        viz_state.containers.bar_cluster.scrollTo({
            top: 0,
            behavior: 'smooth'
        })
    }

    update_cell_layer_id(layers_obj, inst_cat_name)
    update_path_layer_id(layers_obj, inst_cat_name)
    update_trx_layer_id(viz_state.genes, layers_obj)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    viz_state.genes.gene_search_input.value = ''
    update_gene_text_box(viz_state.genes, '')

}

export const ini_cell_layer = async (base_url, viz_state) => {

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    set_cell_names_array(viz_state.cats, cell_arrow_table)

    viz_state.spatial.cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_color_dict_gene(viz_state.genes, base_url)

    set_cell_name_to_index_map(viz_state.cats)

    if (viz_state.cats.has_meta_cell){
        viz_state.cats.cell_cats = viz_state.cats.cell_names_array.map(name => viz_state.cats.meta_cell[name])
    } else {
        // default clustering
        var cluster_arrow_table = await get_arrow_table(base_url + `/cell_clusters/cluster.parquet`, options.fetch)
        set_cell_cats(viz_state.cats, cluster_arrow_table, 'cluster')
    }

    set_dict_cell_cats(viz_state.cats)

    // Combine names and positions into a single array of objects
    const new_cell_names_array = cell_arrow_table.getChild("name").toArray()

    const flatCoordinateArray = viz_state.spatial.cell_scatter_data.attributes.getPosition.value;

    // save cell positions and categories in one place for updating cluster bar plot
    viz_state.combo_data.cell = new_cell_names_array.map((name, index) => ({
        name: name,
        cat: viz_state.cats.dict_cell_cats[name],
        x: flatCoordinateArray[index * 2],
        y: flatCoordinateArray[index * 2 + 1]
    }))


    let cell_scatter_data_objects
    if (viz_state.umap.has_umap){
        let flatCoordinateArray_umap

        flatCoordinateArray_umap = new Float64Array(
            viz_state.cats.cell_names_array.flatMap(cell_id => {

                let coords
                if (!viz_state.umap.umap[cell_id]) {
                    coords = [0, 0];
                } else {
                    coords = viz_state.umap.umap[cell_id];
                }

                return coords;
            })
        );

        // convert to easier to use objects
        const numRows = viz_state.spatial.cell_scatter_data.length; // Replace with arrow_table.numRows
        cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
            position: [flatCoordinateArray[i * 2], flatCoordinateArray[i * 2 + 1]],
            umap: [flatCoordinateArray_umap[i * 2], flatCoordinateArray_umap[i * 2 + 1]]
        }));

        viz_state.spatial.x_min = d3.min(cell_scatter_data_objects.map(d => d.position[0]))
        viz_state.spatial.x_max = d3.max(cell_scatter_data_objects.map(d => d.position[0]))
        viz_state.spatial.y_min = d3.min(cell_scatter_data_objects.map(d => d.position[1]))
        viz_state.spatial.y_max = d3.max(cell_scatter_data_objects.map(d => d.position[1]))

        cell_scatter_data_objects = scale_umap_data(viz_state, cell_scatter_data_objects)


    } else {
        const numRows = viz_state.spatial.cell_scatter_data.length; // Replace with arrow_table.numRows
        cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
            position: [flatCoordinateArray[i * 2], flatCoordinateArray[i * 2 + 1]],
        }));

        viz_state.spatial.x_min = d3.min(cell_scatter_data_objects.map(d => d.position[0]))
        viz_state.spatial.x_max = d3.max(cell_scatter_data_objects.map(d => d.position[0]))
        viz_state.spatial.y_min = d3.min(cell_scatter_data_objects.map(d => d.position[1]))
        viz_state.spatial.y_max = d3.max(cell_scatter_data_objects.map(d => d.position[1]))
    }


    viz_state.spatial.center_x = (viz_state.spatial.x_max + viz_state.spatial.x_min) / 2
    viz_state.spatial.center_y = (viz_state.spatial.y_max + viz_state.spatial.y_min) / 2

    viz_state.spatial.data_width = viz_state.spatial.x_max - viz_state.spatial.x_min
    viz_state.spatial.data_height = viz_state.spatial.y_max - viz_state.spatial.y_min



    // get the width and height of the canvas element stored in viz_state.root
    // const canvas_width = viz_state.root.clientWidth
    // const canvas_height = viz_state.root.clientHeight

    // const canvasElement = viz_state.root.querySelector('#deckgl-overlay');

    // console.log(canvasElement)

    // console.log('root!')
    // console.log(viz_state.root)

    // get the width of viz_state.root
    const root_width = viz_state.root.clientWidth
    const root_height = viz_state.root.clientHeight

    console.log('root_width', root_width)
    console.log('root_height', root_height)


    console.log(viz_state.containers.root_dim.width, viz_state.containers.root_dim.height)

    const canvas_width = viz_state.root.clientWidth // 1000
    const canvas_height = viz_state.containers.root_dim.height //500



    viz_state.spatial.scale_x = canvas_width / viz_state.spatial.data_width
    viz_state.spatial.scale_y = canvas_height / viz_state.spatial.data_height
    viz_state.spatial.scale = Math.min(viz_state.spatial.scale_x, viz_state.spatial.scale_y)

    viz_state.spatial.ini_zoom = Math.log2(viz_state.spatial.scale) * 1.01
    viz_state.spatial.ini_x = viz_state.spatial.center_x
    viz_state.spatial.ini_y = viz_state.spatial.center_y


    console.log('viz_state.spatial', viz_state.spatial)

    viz_state.spatial.cell_scatter_data_objects = cell_scatter_data_objects

    const transitions = {
        getPosition: {
            duration: 3000,
            easing: d3.easeCubic
        }
    }

    let cell_layer = new ScatterplotLayer({
        id: 'cell-layer',
        radiusMinPixels: 1,
        getRadius: 5.0,
        pickable: true,
        getColor: (i, d) => get_cell_color(viz_state.cats, i, d),
        data: viz_state.spatial.cell_scatter_data_objects,
        transitions: transitions,
        getPosition: d => (viz_state.umap.state ? d.umap : d.position),
        updateTriggers: {
            getPosition: [viz_state.umap.state]
        },
    })

    return cell_layer

}

export const set_cell_layer_onclick = (deck_ist, layers_obj, viz_state) => {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        onClick: (event, d) => cell_layer_onclick(event, d, deck_ist, layers_obj, viz_state)
    })
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

export const update_cell_pickable_state = (layers_obj, pickable) => {
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        pickable: pickable,
    });
}

export const toggle_spatial_umap = (deck_ist, layers_obj, viz_state) => {

    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        updateTriggers: {
            getPosition: [viz_state.umap.state]
        }
    })

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}