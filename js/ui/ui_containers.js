import * as d3 from 'd3'
import { make_button } from "./text_buttons"
import { gene_search, set_gene_search } from "./gene_search"
import { tile_slider, cell_slider, trx_slider, ini_slider, ini_slider_params } from './sliders'
import { image_info } from "../global_variables/image_info"
import { image_layer_sliders, make_img_layer_slider_callback, toggle_slider } from "./sliders"
import { debounce } from '../utils/debounce'
import { toggle_visibility_image_layers } from '../deck-gl/image_layers'
import { bar_plot_container, make_bar_plot } from './bar_plot'

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
    ui_container.style.justifyContent = 'space-between'
    return ui_container
}

export const make_ctrl_container = () => {
    let ctrl_container = document.createElement("div")
    ctrl_container.style.display = "flex"
    ctrl_container.style.flexDirection = "row"
    ctrl_container.className = "ctrl_container"
    // ctrl_container.style.width = "190px"
    // ctrl_container.style.margin = "5px"
    return ctrl_container
}

export const flex_container = (class_name, flex_direction, margin=5, height=null) => {
    const container = document.createElement("div")
    container.className = class_name
    container.style.width = "100%"

    if (flex_direction === 'row'){
        container.style.marginLeft = margin + "px"
        container.style.marginRight = margin + "px"
    } else {
        container.style.marginTop = margin + "px"
        container.style.marginBottom = margin + "px"
    }

    container.style.display = "flex"
    container.style.flexDirection = flex_direction

    if (height !== null){
        // container.style.marginLeft = '5px'
        container.style.height = height + 'px'
        container.style.overflow = 'scroll'
        // container.style.border = "1px solid #d3d3d3"
    }

    return container
}

export const make_slider_container = (class_name) => {
    const slider_container = document.createElement("div")
    slider_container.className = class_name
    slider_container.style.width = "100%"
    slider_container.style.marginLeft = "5px"
    slider_container.style.marginTop = "5px"
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
    ui_container.appendChild(gene_search)

    tile_container.appendChild(tile_slider_container)

    ctrl_container.appendChild(image_container)
    ctrl_container.appendChild(tile_container)

    return ui_container

}

export const make_ist_ui_container = (dataset_name) => {

    const ui_container = make_ui_container()
    const ctrl_container = make_ctrl_container()
    image_container = flex_container('image_container', 'row')

    const img_layers_container = flex_container('img_layers_container', 'column', 0, 65)
    img_layers_container.style.width = '155px'

    const cell_container = flex_container('cell_container', 'row')
    cell_container.style.marginLeft = '0px'

    // gene container will contain trx button/slider and gene search
    const gene_container = flex_container('gene_container', 'column')
    gene_container.style.marginTop = '0px'
    const trx_container = flex_container('trx_container', 'row')

    const cell_slider_container = make_slider_container('cell_slider_container')
    const trx_slider_container = make_slider_container('trx_slider_container')

    make_button(image_container, 'ist', 'IMG', 'blue', 30)

    const get_slider_by_name = (name) => {
        return image_layer_sliders.filter(slider => slider.name === name);
    };


    const make_img_layer_ctrl = (inst_image) => {

        const inst_name = inst_image.button_name

        let inst_container = flex_container('img_layer_container', 'row')

        make_button(inst_container, 'ist', inst_name, 'blue', 100, 'img_layer_button')

        const inst_slider_container = make_slider_container(inst_name)

        let slider
        if (inst_name === 'DAPI'){
            // slider = dapi_slider
            slider = get_slider_by_name('DAPI')[0]
        } else {
            // slider = bound_slider
            slider = get_slider_by_name('BOUND')[0]
        }

        let img_layer_slider_callback = make_img_layer_slider_callback(inst_name)

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

    make_button(cell_container, 'ist', 'CELL')
    make_button(trx_container, 'ist', 'TRX')

    image_container.appendChild(img_layers_container)

    ini_slider('cell')
    cell_container.appendChild(cell_slider_container)
    cell_slider_container.appendChild(cell_slider)

    ini_slider('trx')
    trx_container.appendChild(trx_slider_container)
    trx_slider_container.appendChild(trx_slider)

    gene_container.appendChild(trx_container)

    set_gene_search('ist')

    gene_search.style.marginLeft = '10px'

    gene_container.appendChild(gene_search)

    ui_container.appendChild(ctrl_container)

    ctrl_container.appendChild(image_container)
    ctrl_container.appendChild(cell_container)
    ctrl_container.appendChild(gene_container)

    make_bar_plot()
    console.log('appending bar plot container')
    ctrl_container.appendChild(bar_plot_container)

    // if dataset_name is not an empty string make the name container
    if (dataset_name.trim !== ''){

        let name_container = document.createElement("div")

        d3.select(name_container)
            .classed('name_container', true)
            .style('width', '100px')
            .style('text-align', 'right')
            .style('cursor', 'pointer')
            .style('font-size', '14px')
            .style('font-weight', 'bold')
            .style('color', '#222222')
            .style('margin-top', '5px')
            .style('margin-right', '5px')
            .style('user-select', 'none')
            .text(dataset_name.toUpperCase())

        ui_container.appendChild(name_container)

    }

    return ui_container

}