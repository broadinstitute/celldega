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

    // toggle_spatial_umap(deck_ist, layers_obj, viz_state)

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

    const cell_scatter_data = get_scatter_data(cell_arrow_table)

    // ('cell_scatter_data.attributes', cell_scatter_data.attributes)

    viz_state.umap.cell_scatter_data = cell_scatter_data


    let coords
    let cell_umap_data
    let flatCoordinateArray_umap
    // let cell_scatter_data
    if (viz_state.umap.has_umap){

        flatCoordinateArray_umap = new Float64Array(
            viz_state.cats.cell_names_array.flatMap(cell_id => {

                if (!viz_state.umap.umap[cell_id]) {
                    coords = [0, 0];
                } else {
                    coords = viz_state.umap.umap[cell_id];
                }

                return coords; // Add UMAP coordinates [x, y]
            })
        );

        cell_scatter_data.attributes.getUMAP = {
            value: flatCoordinateArray_umap,
            size: 2
        }

        // // Create the scatter_data object
        // cell_umap_data = {
        //     length: viz_state.cats.cell_names_array.length,
        //     attributes: {
        //         getPosition: { value: flatCoordinateArray_umap, size: 2 },
        //     }
        // };

        // viz_state.umap.cell_umap_data = cell_umap_data

    }



    console.log('checking if additional attribute is available')
    console.log("cell_scatter_data", cell_scatter_data)

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

    const flatCoordinateArray = cell_scatter_data.attributes.getPosition.value;
    // const flatCoordinateArray = cell_scatter_data.attributes.position.value;

    // save cell positions and categories in one place for updating cluster bar plot
    viz_state.combo_data.cell = new_cell_names_array.map((name, index) => ({
        name: name,
        cat: viz_state.cats.dict_cell_cats[name],
        x: flatCoordinateArray[index * 2],
        y: flatCoordinateArray[index * 2 + 1]
    }))

    // console.log("Scatter data length:", cell_scatter_data.length);
    // console.log("Scatter data position size:", cell_scatter_data.attributes.getPosition.size);
    // console.log("Scatter data value length:", cell_scatter_data.attributes.getPosition.value.length);
    // console.log("Expected value length:", cell_scatter_data.length * cell_scatter_data.attributes.getPosition.size);

    // console.log("UMAP data length:", cell_umap_data.length);
    // console.log("UMAP data position size:", cell_umap_data.attributes.getPosition.size);
    // console.log("UMAP data value length:", cell_umap_data.attributes.getPosition.value.length);
    // console.log("Expected value length:", cell_umap_data.length * cell_umap_data.attributes.getPosition.size);


    const transitions = {
        getRadius: {
            duration: 3000,
            easing: d3.easeCubic
        },
        getPosition: {
            duration: 3000,
            easing: d3.easeCubic
        }
    }

    console.log('**************')


    // convert to easier to use objects
    const numRows = cell_scatter_data.length; // Replace with arrow_table.numRows
    // const flatCoordinateArray = cell_scatter_data.attributes.getPosition.value; // Flat array

    const cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
      position: [flatCoordinateArray[i * 2], flatCoordinateArray[i * 2 + 1]],
      umap: [flatCoordinateArray_umap[i * 2], flatCoordinateArray_umap[i * 2 + 1]]
    }));

    // scale umap values to be centered around the middle of the image x and y positions (max - min / 2)
    // use d3 to find the min and max of the flatCoordinateArray

    const x_min = d3.min(cell_scatter_data_objects.map(d => d.position[0]))
    const x_max = d3.max(cell_scatter_data_objects.map(d => d.position[0]))
    const y_min = d3.min(cell_scatter_data_objects.map(d => d.position[1]))
    const y_max = d3.max(cell_scatter_data_objects.map(d => d.position[1]))

    // take the smaller of the two ranges for x and y
    const x_range = x_max - x_min
    const y_range = y_max - y_min

    const range_min = Math.min(x_range, y_range)

    const x_mid = (x_max - x_min) / 2;
    const y_mid = (y_max - y_min) / 2;

    let umap_x_min = d3.min(cell_scatter_data_objects.map(d => d.umap[0]))
    let umap_x_max = d3.max(cell_scatter_data_objects.map(d => d.umap[0]))
    let umap_y_min = d3.min(cell_scatter_data_objects.map(d => d.umap[1]))
    let umap_y_max = d3.max(cell_scatter_data_objects.map(d => d.umap[1]))

    const umap_x_range = umap_x_max - umap_x_min
    const umap_y_range = umap_y_max - umap_y_min

    // scale the umap values to be within range_min and c   entered about x_mid and y_mid
    cell_scatter_data_objects.forEach(d => {
        d.umap[0] = (d.umap[0] - umap_x_min) / (umap_x_range) * range_min
        d.umap[1] = (d.umap[1] - umap_y_min) / (umap_y_range) * range_min
    })

    umap_x_min = d3.min(cell_scatter_data_objects.map(d => d.umap[0]))
    umap_x_max = d3.max(cell_scatter_data_objects.map(d => d.umap[0]))
    umap_y_min = d3.min(cell_scatter_data_objects.map(d => d.umap[1]))
    umap_y_max = d3.max(cell_scatter_data_objects.map(d => d.umap[1]))

    const umap_x_mid = (umap_x_max - umap_x_min) / 2;
    const umap_y_mid = (umap_y_max - umap_y_min) / 2;

    const x_diff = x_mid - umap_x_mid;
    const y_diff = y_mid - umap_y_mid;

    // apply this to cell_scatter_data_objects
    cell_scatter_data_objects.forEach((d) => {
        d.umap[0] = d.umap[0] + x_diff;
        d.umap[1] = d.umap[1] + y_diff;
    })




    console.log('viz_state.umap.state', viz_state.umap.state)

    let cell_layer = new ScatterplotLayer({
        id: 'cell-layer',
        radiusMinPixels: 1,
        getRadius: 5.0,
        pickable: true,
        getColor: (i, d) => get_cell_color(viz_state.cats, i, d),
        data: cell_scatter_data_objects,
        // data: cell_umap_data,
        transitions: transitions,
        // getPosition: d => {
        //     // console.log(d)
        //     return d.position
        // }
        getPosition: d => (viz_state.umap.state ? d.umap : d.position),
        // getPosition: d => [d.attributes.getPosition.value[0], d.attributes.getPosition.value[0]],
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

    console.log('viz_state.umap.state', viz_state.umap.state)

    const transitions = {
        getRadius: {
            duration: 3000,
            easing: d3.easeCubic
        },
        getPosition: {
            duration: 3000,
            easing: d3.easeCubic
        }
    }


    layers_obj.cell_layer = layers_obj.cell_layer.clone({
        // id: 'cell-layer-umap',
        // data: viz_state.umap.state ? viz_state.umap.cell_umap_data : viz_state.umap.cell_scatter_data,
        // getRadius: 200,
        // getPosition: d => d.umap,
        // getPosition: d => [d.attributes.getUMAP.value[0], d.attributes.getUMAP.value[1]]
        updateTriggers: {
            getPosition: [viz_state.umap.state]
        },
        transitions: transitions,
    })

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

}