import * as d3 from 'd3'
import { make_button } from "./text_buttons"
import { gene_search, set_gene_search } from "./gene_search"
import { tile_slider, cell_slider, trx_slider, ini_slider, ini_slider_params } from './sliders'
import { image_info } from "../global_variables/image_info"
import { image_layer_sliders, make_img_layer_slider_callback, toggle_slider } from "./sliders"
import { debounce } from '../utils/debounce'
import { toggle_visibility_image_layers } from '../deck-gl/image_layers'
import { make_bar_graph } from './bar_plot'
import { bar_container_cluster, bar_callback_cluster, svg_bar_cluster } from './bar_plot'
import { bar_container_gene, bar_callback_gene, svg_bar_gene } from './bar_plot'
import { cluster_counts } from '../global_variables/meta_cluster'
import { color_dict_cluster } from '../global_variables/meta_cluster'
import { color_dict_gene } from '../global_variables/color_dict_gene'
import { gene_counts } from '../global_variables/meta_gene'

export let image_container

export const toggle_image_layers_and_ctrls = (is_visible) => {
    d3.select(image_container)
        .selectAll('.img_layer_button')
        .style('color', is_visible ? 'blue' : 'gray');

    image_layer_sliders.map(slider => toggle_slider(slider, is_visible))
    toggle_visibility_image_layers(is_visible)
}

export const make_ui_container = () => {
    const ui_container = document.createElement("div")
    ui_container.style.display = "flex"
    ui_container.style.flexDirection = "row"
    ui_container.style.border = "1px solid #d3d3d3"
    ui_container.className = "ui_container"
    // ui_container.style.justifyContent = 'space-between'
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

export const make_sst_ui_container = () => {

    const ui_container = make_ui_container()
    const ctrl_container = make_ctrl_container()
    const image_container = flex_container('image_container', 'row')
    const tile_container = flex_container('tile_container', 'row')
    const tile_slider_container = make_slider_container('tile_slider_container')

    make_button(image_container, 'sst', 'IMG', 'blue', 50)
    make_button(tile_container, 'sst', 'TILE')

    ini_slider('tile')
    tile_slider_container.appendChild(tile_slider);

    ui_container.appendChild(ctrl_container)

    tile_container.appendChild(tile_slider_container)

    ctrl_container.appendChild(image_container)
    ctrl_container.appendChild(tile_container)

    return ui_container

}

export const make_ist_ui_container = (dataset_name, deck_ist, layers_obj) => {

    const ui_container = make_ui_container()
    const ctrl_container = make_ctrl_container()

    // image_container = flex_container('image_container', 'row')
    image_container = flex_container('image_container', 'column')

    const img_layers_container = flex_container('img_layers_container', 'column', 72) // 75
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

    make_button(image_container, 'ist', 'IMG', 'blue', 30, 'button', deck_ist)

    const get_slider_by_name = (name) => {
        return image_layer_sliders.filter(slider => slider.name === name);
    };


    const make_img_layer_ctrl = (inst_image) => {

        const inst_name = inst_image.button_name

        let inst_container = flex_container('image_layer_container', 'row')
        inst_container.style.height = '21px'

        make_button(inst_container, 'ist', inst_name, 'blue', 75, 'img_layer_button', deck_ist)

        const inst_slider_container = make_slider_container(inst_name)

        let slider = get_slider_by_name(inst_name)[0]

        let img_layer_slider_callback = make_img_layer_slider_callback(inst_name, deck_ist)

        const debounce_time = 100
        let img_layer_slider_callback_debounced = debounce(img_layer_slider_callback, debounce_time)
        const ini_img_slider_value = 50
        ini_slider_params(slider, ini_img_slider_value, img_layer_slider_callback_debounced)

        inst_slider_container.appendChild(slider)

        inst_container.appendChild(inst_slider_container)

        img_layers_container.appendChild(inst_container)

    }

    image_info.map(
        make_img_layer_ctrl
    )

    make_button(cell_ctrl_container, 'ist', 'CELL', 'blue', 40, 'button', deck_ist)
    make_button(      trx_container, 'ist', 'TRX',  'blue', 40, 'button', deck_ist)

    image_container.appendChild(img_layers_container)

    ini_slider('cell', deck_ist)
    cell_slider_container.appendChild(cell_slider)
    cell_ctrl_container.appendChild(cell_slider_container)

    make_bar_graph(
        bar_container_cluster,
        bar_callback_cluster,
        svg_bar_cluster,
        cluster_counts,
        color_dict_cluster,
        deck_ist,
        layers_obj
    )

    make_bar_graph(
        bar_container_gene,
        bar_callback_gene,
        svg_bar_gene,
        gene_counts,
        color_dict_gene,
        deck_ist,
        layers_obj
    )

    cell_container.appendChild(cell_ctrl_container)
    cell_container.appendChild(bar_container_cluster)

    ini_slider('trx', deck_ist)
    trx_container.appendChild(trx_slider_container)
    trx_slider_container.appendChild(trx_slider)

    gene_container.appendChild(trx_container)
    gene_container.appendChild(bar_container_gene)

    set_gene_search('ist', deck_ist)

    gene_search.style.marginLeft = '0px'

    ui_container.appendChild(ctrl_container)

    ctrl_container.appendChild(image_container)
    ctrl_container.appendChild(cell_container)
    ctrl_container.appendChild(gene_container)

    ctrl_container.appendChild(gene_search)


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