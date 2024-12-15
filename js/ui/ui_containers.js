import * as d3 from 'd3'
import { make_button, make_edit_button, make_reorder_button } from "./text_buttons"
import { set_gene_search } from "./gene_search"
import { ini_slider, ini_slider_params } from './sliders'
import { make_img_layer_slider_callback, toggle_slider } from "./sliders"
import { debounce } from '../utils/debounce'
import { toggle_visibility_image_layers } from '../deck-gl/image_layers'
import { make_bar_graph, bar_callback_rgn, bar_callback_cluster, make_bar_container, bar_callback_gene } from './bar_plot'
import { calc_dendro_triangles, calc_dendro_polygons, alt_slice_linkage } from '../matrix/dendro'
import { update_dendro_layer_data } from '../deck-gl/matrix/dendro_layers'
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers'
import { DrawPolygonMode, ViewMode} from '@deck.gl-community/editable-layers'
import { update_edit_layer_mode, update_edit_visitility, calc_and_update_rgn_bar_graph, sync_region_to_model } from '../deck-gl/edit_layer'
import { get_layers_list } from '../deck-gl/layers_ist'
import { update_cell_pickable_state } from '../deck-gl/cell_layer'
import { toggle_trx_layer_visibility, update_trx_pickable_state } from '../deck-gl/trx_layer'
import { update_path_pickable_state } from '../deck-gl/path_layer'
import { toggle_nbhd_layer_visibility } from '../deck-gl/nbhd_layer'
import { toggle_background_layer_visibility } from '../deck-gl/background_layer'


export const toggle_image_layers_and_ctrls = (layers_obj, viz_state, is_visible) => {

    d3.select(viz_state.containers.image)
        .selectAll('.img_layer_button')
        .style('color', is_visible ? 'blue' : 'gray');

    viz_state.img.image_layer_sliders.map(slider => toggle_slider(slider, is_visible))
    toggle_visibility_image_layers(layers_obj, is_visible)
}

export const make_ui_container = () => {
    const ui_container = document.createElement("div")
    ui_container.style.display = "flex"
    ui_container.style.flexDirection = "row"
    ui_container.style.border = "1px solid #d3d3d3"
    ui_container.className = "ui_container"
    ui_container.style.height = '100px' // '85px'
    return ui_container
}

export const make_ctrl_container = () => {
    let ctrl_container = document.createElement("div")
    ctrl_container.style.display = "flex"
    ctrl_container.style.flexDirection = "row"
    ctrl_container.className = "ctrl_container"
    ctrl_container.style.width = '535px'
    return ctrl_container
}

export const flex_container = (class_name, flex_direction, height=null) => {
    const container = document.createElement("div")
    container.className = class_name

    container.style.display = "flex"
    container.style.flexDirection = flex_direction

    if (height !== null){
        container.style.height = height + 'px'
        container.style.overflow = 'scroll'
    }

    return container
}

export const make_slider_container = (class_name) => {
    const slider_container = document.createElement("div")
    slider_container.className = class_name
    slider_container.style.width = "100%"
    slider_container.style.marginLeft = "2px"
    slider_container.style.marginTop = "2px"
    return slider_container
}

export const make_matrix_ui_container = (deck_mat, layers_mat, viz_state) => {

    const ui_container = make_ui_container()
    const ctrl_container = flex_container('button_container', 'column')

    const slider_container = flex_container('slider_container', 'column')

    const button_width = 33

    const axes = ['col', 'row']

    const inst_orders = ['clust', 'sum', 'var', 'ini']

    axes.forEach(axis => {

        const inst_container = flex_container(axis, 'row')

        d3.select(inst_container)
            .append('div')
            .text(axis.toUpperCase())
            .style('width', button_width + 'px')
            .style('height', '20px')  // Adjust height for button padding
            .style('display', 'inline-flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('text-align', 'center')
            .style('cursor', 'pointer')
            .style('font-size', '12px')
            .style('font-weight', 'bold')
            .style('color', '#47515b')
            .style('border', '3px solid')  // Light gray border
            .style('border-color', 'white')  // Light gray border
            .style('border-radius', '12px')  // Rounded corners
            .style('margin-top', '5px')
            .style('margin-left', '5px')
            .style('padding', '4px 10px')  // Padding inside the button
            .style('user-select', 'none')
            .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')

        inst_orders.forEach((label) => {
            const isClust = label === 'clust';
            make_reorder_button(inst_container, label, isClust, button_width, axis, deck_mat, layers_mat, viz_state);
        });

        ctrl_container.appendChild(inst_container)
    })

    viz_state.dendro.sliders = {};

    axes.forEach(axis => {

        viz_state.dendro.sliders[axis] = document.createElement("input")
        viz_state.dendro.sliders[axis].type = "range"
        viz_state.dendro.sliders[axis].min = "0"
        viz_state.dendro.sliders[axis].max = "100"
        viz_state.dendro.sliders[axis].value = 50
        viz_state.dendro.sliders[axis].className = "slider"
        viz_state.dendro.sliders[axis].style.width = "75px"

    });

    const dendro_slider_callback = (deck_mat, viz_state, axis, event) => {

        // Update the dendrogram layer
        viz_state.dendro.sliders[axis + '_value'] = viz_state.dendro.max_linkage_dist[axis] * event.target.value/100

        alt_slice_linkage(viz_state, axis, viz_state.dendro.sliders[axis + '_value'])
        calc_dendro_triangles(viz_state, axis);
        calc_dendro_polygons(viz_state, axis);
        update_dendro_layer_data(layers_mat, viz_state, axis)

        deck_mat.setProps({
            layers: get_mat_layers_list(layers_mat),
        })

    };

    // Add event listener to log the slider value
    axes.forEach(axis => {
        viz_state.dendro.sliders[axis].addEventListener("input", (event) => dendro_slider_callback(deck_mat, viz_state, axis, event))
    });

    viz_state.dendro.sliders.col.style.marginTop = '5px'
    viz_state.dendro.sliders.row.style.marginTop = '20px'


    d3.select(slider_container)
        .append('div')
        .text('DENDRO')
        .style('width', button_width + 'px')
        .style('height', '20px')  // Adjust height for button padding
        .style('display', 'inline-flex')
        .style('align-items', 'center')
        .style('justify-content', 'center')
        .style('text-align', 'center')
        .style('cursor', 'pointer')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .style('color', '#47515b')
        .style('border', '3px solid')  // Light gray border
        .style('border-color', 'white')  // Light gray border
        .style('border-radius', '12px')  // Rounded corners
        // .style('margin-top', '5px')
        .style('margin-left', '20px')
        // .style('padding', '4px 10px')  // Padding inside the button
        .style('user-select', 'none')
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')

    slider_container.appendChild(viz_state.dendro.sliders.col)
    slider_container.appendChild(viz_state.dendro.sliders.row)

    // add top margin to ctrl_container and slider_container
    ctrl_container.style.marginTop = '15px'
    slider_container.style.marginTop = '0px'
    slider_container.style.marginLeft = '10px'

    ui_container.appendChild(ctrl_container)
    ui_container.appendChild(slider_container)

    return ui_container

}




export const make_sst_ui_container = (deck_sst, layers_sst, viz_state) => {

    const ui_container = make_ui_container()
    const ctrl_container = make_ctrl_container()
    const image_container = flex_container('image_container', 'row')
    const tile_container = flex_container('tile_container', 'row')
    const tile_slider_container = make_slider_container('tile_slider_container')

    make_button(image_container, 'sst', 'IMG', 'blue', 50, 'button', deck_sst, layers_sst, viz_state)
    make_button(tile_container, 'sst', 'TILE', 'blue', 50, 'button', deck_sst, layers_sst, viz_state)

    viz_state.sliders = {}

    ini_slider('tile', deck_sst, layers_sst, viz_state)

    tile_slider_container.appendChild(viz_state.sliders.tile);

    ui_container.appendChild(ctrl_container)

    tile_container.appendChild(tile_slider_container)

    set_gene_search('sst', deck_sst, layers_sst, viz_state)

    ctrl_container.appendChild(image_container)
    ctrl_container.appendChild(tile_container)
    ctrl_container.appendChild(viz_state.genes.gene_search)

    return ui_container

}

export const make_ist_ui_container = (dataset_name, deck_ist, layers_obj, viz_state) => {

    const ui_container = make_ui_container()
    const ctrl_container = make_ctrl_container()

    viz_state.containers.image = flex_container('image_container', 'column')

    const img_layers_container = flex_container('img_layers_container', 'column', 72)
    img_layers_container.style.width = '135px'
    img_layers_container.style.border = "1px solid #d3d3d3"
    img_layers_container.style.marginTop = '3px'
    img_layers_container.style.marginLeft = '2px'

    img_layers_container.addEventListener('wheel', (event) => {
        const { scrollTop, scrollHeight, clientHeight } = img_layers_container
        const atTop = scrollTop === 0
        const atBottom = scrollTop + clientHeight === scrollHeight

        if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
            event.preventDefault()
        }
    })

    const bar_container_width = '115px'

    const cell_container = flex_container('cell_container', 'column')
    // widths are custom because of the length of the text buttons varies
    cell_container.style.width = bar_container_width
    const cell_ctrl_container = flex_container('cell_ctrl_container', 'row')
    cell_ctrl_container.style.marginLeft = '0px'

    // gene container will contain trx button/slider and gene search
    const gene_container = flex_container('gene_container', 'column')
    gene_container.style.marginTop = '0px'
    gene_container.style.width = bar_container_width
    const trx_container = flex_container('trx_container', 'row')

    const rgn_container = flex_container('rgn_container', 'column')
    rgn_container.style.width = bar_container_width
    const rgn_ctrl_container = flex_container('rgn_ctrl_container', 'row')
    rgn_ctrl_container.style.marginLeft = '0px'
    rgn_ctrl_container.style.height = '22.5px'

    const cell_slider_container = make_slider_container('cell_slider_container')
    const trx_slider_container = make_slider_container('trx_slider_container')

    make_button(viz_state.containers.image, 'ist', 'IMG', 'blue', 30, 'button', deck_ist, layers_obj, viz_state)

    const get_slider_by_name = (img, name) => {
        return img.image_layer_sliders.filter(slider => slider.name === name);
    };

    const make_img_layer_ctrl = (img, inst_image) => {

        const inst_name = inst_image.button_name

        let inst_container = flex_container('image_layer_container', 'row')
        inst_container.style.height = '21px'

        make_button(inst_container, 'ist', inst_name, 'blue', 75, 'img_layer_button', deck_ist, layers_obj, viz_state)

        const inst_slider_container = make_slider_container(inst_name)

        let slider = get_slider_by_name(img, inst_name)[0]

        let img_layer_slider_callback = make_img_layer_slider_callback(inst_name, deck_ist, layers_obj, viz_state)

        const debounce_time = 100
        let img_layer_slider_callback_debounced = debounce(img_layer_slider_callback, debounce_time)
        const ini_img_slider_value = 50
        ini_slider_params(slider, ini_img_slider_value, img_layer_slider_callback_debounced)

        inst_slider_container.appendChild(slider)

        inst_container.appendChild(inst_slider_container)

        img_layers_container.appendChild(inst_container)

    }

    viz_state.img.image_info.map(inst_image => make_img_layer_ctrl(viz_state.img, inst_image))

    make_button(cell_ctrl_container, 'ist', 'CELL', 'blue', 40, 'button', deck_ist, layers_obj, viz_state)
    make_button(      trx_container, 'ist', 'TRX',  'blue', 40, 'button', deck_ist, layers_obj, viz_state)

    viz_state.containers.image.appendChild(img_layers_container)

    viz_state.sliders = {}

    ini_slider('cell', deck_ist, layers_obj, viz_state)

    cell_slider_container.appendChild(viz_state.sliders.cell)
    cell_ctrl_container.appendChild(cell_slider_container)

    viz_state.containers.bar_cluster = make_bar_container()

    make_bar_graph(
        viz_state.containers.bar_cluster,
        bar_callback_cluster,
        viz_state.cats.svg_bar_cluster,
        viz_state.cats.cluster_counts,
        viz_state.cats.color_dict_cluster,
        deck_ist,
        layers_obj,
        viz_state
    )

    viz_state.containers.bar_gene = make_bar_container()

    make_bar_graph(
        viz_state.containers.bar_gene,
        bar_callback_gene,
        viz_state.genes.svg_bar_gene,
        viz_state.genes.gene_counts,
        viz_state.genes.color_dict_gene,
        deck_ist,
        layers_obj,
        viz_state
    )

    cell_container.appendChild(cell_ctrl_container)
    cell_container.appendChild(viz_state.containers.bar_cluster)

    ini_slider('trx', deck_ist, layers_obj, viz_state)
    trx_container.appendChild(trx_slider_container)
    trx_slider_container.appendChild(viz_state.sliders.trx)



    gene_container.appendChild(trx_container)
    gene_container.appendChild(viz_state.containers.bar_gene)

    set_gene_search('ist', deck_ist, layers_obj, viz_state)

    viz_state.genes.gene_search.style.marginLeft = '0px'

    ui_container.appendChild(ctrl_container)

    ctrl_container.appendChild(viz_state.containers.image)
    ctrl_container.appendChild(cell_container)
    ctrl_container.appendChild(gene_container)

    viz_state.genes.gene_search.style.width = '160px'
    viz_state.genes.gene_search.style.marginLeft = '5px'

    // ctrl_container.appendChild(viz_state.genes.gene_search)

    const sketch_callback = (event, deck_ist, layers_obj, viz_state) => {

        const current = d3.select(event.currentTarget)
        const is_active = current.classed('active')
        // let button_name = current.text().toLowerCase()

        // clicking sketch should always return the rgn to visible
        viz_state.edit.visible = true
        current.classed('active', viz_state.edit.visible)
            .style('color', 'blue')

        d3.select(viz_state.edit.buttons.rgn)
            .style('color', 'blue')
            .classed('active', true)


        update_edit_visitility(layers_obj, viz_state.edit.visible)

        if (is_active === false) {

            current.classed('active', true)
                   .style('color', 'blue')

            viz_state.edit.mode = 'sktch'

            update_edit_layer_mode(layers_obj, DrawPolygonMode)
            update_cell_pickable_state(layers_obj, false)
            update_path_pickable_state(layers_obj, false)
            update_trx_pickable_state(layers_obj, false)
            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})


        } else if (is_active === true) {

            viz_state.edit.mode = 'view'

            current.classed('active', false)
                   .style('color', 'gray')

            update_edit_layer_mode(layers_obj, ViewMode)
            update_cell_pickable_state(layers_obj, true)
            update_path_pickable_state(layers_obj, true)
            update_trx_pickable_state(layers_obj, true)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

        }
    }

    const rgn_callback = (event, deck_ist, layers_obj, viz_state) => {
        const current = d3.select(event.currentTarget)
        const is_active = current.classed('active')

        if (is_active === false) {
            viz_state.edit.visible = true

            current.classed('active', viz_state.edit.visible)
                .style('color', 'blue')


        } else {
            viz_state.edit.visible = false

            current.classed('active', viz_state.edit.visible)
                .style('color', 'gray')

        }

        update_edit_visitility(layers_obj, viz_state.edit.visible)
        const layers_list = get_layers_list(layers_obj, viz_state.close_up)
        deck_ist.setProps({layers: layers_list})

    }

    const delete_polygon_index = (featureCollection, index) => {
        if (index >= 0 && index < featureCollection.features.length) {
          featureCollection.features.splice(index, 1); // Remove the feature at the given index
        //   console.log(`Feature at index ${index} deleted.`);
        } else {
        //   console.warn(`Invalid index: ${index}. No feature deleted.`);
        }

        return featureCollection; // Return the updated FeatureCollection
      };


    const del_callback = (event, deck_ist, layers_obj, viz_state) => {

        viz_state.edit.feature_collection = delete_polygon_index(
            viz_state.edit.feature_collection,
            viz_state.edit.modify_index
        )

        // switch to view mode
        layers_obj.edit_layer = layers_obj.edit_layer.clone({
            id: 'edit-layer-delete',
            data: viz_state.edit.feature_collection,
            mode: ViewMode,
            selectedFeatureIndexes: [],
        })

        const layers_list = get_layers_list(layers_obj, viz_state.close_up)
        deck_ist.setProps({layers: layers_list})

        // hide the DEL button
        d3.select(viz_state.edit.buttons.del)
            .classed('active', false)
            .style('display', 'none')

        // hide the RGN and SKTCH buttons
        d3.select(viz_state.edit.buttons.rgn)
          .style('display', 'inline-flex');

        d3.select(viz_state.edit.buttons.sktch)
            .style('display', 'inline-flex');

        calc_and_update_rgn_bar_graph(viz_state, deck_ist, layers_obj)

        sync_region_to_model(viz_state)


    }

    const alph_callback = (event, deck_ist, layers_obj, viz_state) => {

        if (viz_state.nbhd.visible === true){
            viz_state.nbhd.visible = false
        } else {
            viz_state.nbhd.visible = true
        }

        toggle_nbhd_layer_visibility(layers_obj, viz_state.nbhd.visible)

        // toggle with the opposite of viz_state.nbhd.visible
        toggle_trx_layer_visibility(layers_obj, viz_state.nbhd.visible===true ? false : true)
        toggle_visibility_image_layers(layers_obj, viz_state.nbhd.visible===true ? false : true)
        toggle_background_layer_visibility(layers_obj, viz_state.nbhd.visible===true ? false : true)

        const layers_list = get_layers_list(layers_obj, viz_state.close_up, viz_state.nbhd.visible)
        deck_ist.setProps({layers: layers_list})

    }


    viz_state.edit.buttons = {}
    viz_state.edit.mode = 'view'
    make_edit_button(deck_ist, layers_obj, viz_state, rgn_ctrl_container, 'RGN', 30, rgn_callback)
    make_edit_button(deck_ist, layers_obj, viz_state, rgn_ctrl_container, 'ALPH', 30, alph_callback)
    make_edit_button(deck_ist, layers_obj, viz_state, rgn_ctrl_container, 'SKTCH', 40, sketch_callback)
    make_edit_button(deck_ist, layers_obj, viz_state, rgn_ctrl_container, 'DEL', 30, del_callback)

    // // initially do not display the RGN button
    // d3.select(viz_state.edit.buttons.rgn)
    //     .style('display', 'none')

    // initially hide the DEL delete button
    d3.select(viz_state.edit.buttons.del)
        .style('color', 'red')
        .style('display', 'none')

    viz_state.containers.bar_rgn = make_bar_container()
    viz_state.containers.bar_rgn.style.marginLeft = '0px'

    rgn_container.appendChild(rgn_ctrl_container)
    rgn_container.appendChild(viz_state.containers.bar_rgn)

    ctrl_container.appendChild(rgn_container)

    ctrl_container.appendChild(viz_state.genes.gene_search)

    make_bar_graph(
        viz_state.containers.bar_rgn,
        bar_callback_rgn,
        viz_state.edit.svg_bar_rgn,
        viz_state.edit.rgn_areas,
        viz_state.edit.color_dict_rgn,
        deck_ist,
        layers_obj,
        viz_state
    )

    // ctrl_container.append(viz_state.containers.bar_rgn)

    // viz_state.edit.buttons.rgn.style.color = 'red'

    // // if dataset_name is not an empty string make the name container
    // if (dataset_name.trim !== ''){

    //     let name_container = document.createElement("div")

    //     d3.select(name_container)
    //         .classed('name_container', true)
    //         // .style('width', '100px')
    //         .style('text-align', 'left')
    //         .style('cursor', 'pointer')
    //         .style('font-size', '22px')
    //         .style('font-weight', 'bold')
    //         .style('color', '#222222')
    //         .style('margin-top', '0px')
    //         .style('margin-left', '15px')
    //         .style('margin-right', '5px')
    //         .style('user-select', 'none')
    //         .text(dataset_name.toUpperCase())

    //     ui_container.appendChild(name_container)

    // }

    return ui_container

}

