import * as d3 from 'd3'
import { make_button, make_reorder_button } from "./text_buttons"
import { set_gene_search } from "./gene_search"
import { ini_slider, ini_slider_params } from './sliders'
import { make_img_layer_slider_callback, toggle_slider } from "./sliders"
import { debounce } from '../utils/debounce'
import { toggle_visibility_image_layers } from '../deck-gl/image_layers'
import { make_bar_graph } from './bar_plot'
import { bar_callback_cluster, make_bar_container } from './bar_plot'
import { bar_callback_gene } from './bar_plot'

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

    ui_container.appendChild(ctrl_container)

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

    const cell_container = flex_container('cell_container', 'column')
    // widths are custom because of the length of the text buttons varies
    cell_container.style.width = '120px'
    const cell_ctrl_container = flex_container('cell_ctrl_container', 'row')
    cell_ctrl_container.style.marginLeft = '0px'

    // gene container will contain trx button/slider and gene search
    const gene_container = flex_container('gene_container', 'column')
    gene_container.style.marginTop = '0px'
    gene_container.style.width = '125px'
    const trx_container = flex_container('trx_container', 'row')

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

    ctrl_container.appendChild(viz_state.genes.gene_search)

    // if dataset_name is not an empty string make the name container
    if (dataset_name.trim !== ''){

        let name_container = document.createElement("div")

        d3.select(name_container)
            .classed('name_container', true)
            // .style('width', '100px')
            .style('text-align', 'left')
            .style('cursor', 'pointer')
            .style('font-size', '22px')
            .style('font-weight', 'bold')
            .style('color', '#222222')
            .style('margin-top', '0px')
            .style('margin-left', '15px')
            .style('margin-right', '5px')
            .style('user-select', 'none')
            .text(dataset_name.toUpperCase())

        ui_container.appendChild(name_container)

    }

    return ui_container

}