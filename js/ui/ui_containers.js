import { make_button } from "./text_buttons"
import { gene_search } from "./gene_search"
import { tile_slider, cell_slider, trx_slider, ini_slider } from './sliders'

export const make_ui_container = () => {
    const ui_container = document.createElement("div")
    ui_container.style.display = "flex"
    ui_container.style.flexDirection = "row"
    ui_container.style.border = "1px solid #d3d3d3"    
    ui_container.className = "ui_container"
    return ui_container
}

export const make_ctrl_container = () => {
    let ctrl_container = document.createElement("div")
    ctrl_container.style.display = "flex"
    ctrl_container.style.flexDirection = "row"
    ctrl_container.className = "ctrl_container"
    ctrl_container.style.width = "250px"
    ctrl_container.style.margin = "5px"
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
        container.style.marginLeft = '5px'
        container.style.height = height + 'px'
        container.style.overflow = 'scroll'
        container.style.border = "1px solid #d3d3d3"    
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
    const img_container = flex_container('image_container', 'row')
    const tile_container = flex_container('tile_container', 'row')
    const tile_slider_container = make_slider_container('tile_slider_container')

    make_button(img_container, 'sst', 'IMG')
    make_button(tile_container, 'sst', 'TILE')

    ini_slider('tile')
    tile_slider_container.appendChild(tile_slider);

    ui_container.appendChild(ctrl_container)
    ui_container.appendChild(gene_search)    

    tile_container.appendChild(tile_slider_container)

    ctrl_container.appendChild(img_container) 
    ctrl_container.appendChild(tile_container)             

    return ui_container

}

export const make_ist_ui_container = (image_info) => {

    const ui_container = make_ui_container()
    const ctrl_container = make_ctrl_container()
    const img_container = flex_container('img_container', 'row')

    const img_layer_container = flex_container('img_layers_container', 'column', 0, 65)
    img_layer_container.style.width = '200px'

    const cell_container = flex_container('cell_container', 'row')
    const trx_container = flex_container('trx_container', 'row')
    const cell_slider_container = make_slider_container('cell_slider_container')
    const trx_slider_container = make_slider_container('trx_slider_container')

    make_button(img_container, 'ist', 'IMG')

    // make_button(img_layer_container, 'ist', 'IMG')
    // make_button(img_layer_container, 'ist', 'IMG')
    // make_button(img_layer_container, 'ist', 'IMG')
    // make_button(img_layer_container, 'ist', 'IMG')
    // make_button(img_layer_container, 'ist', 'IMG')

    
    image_info.map((inst_image) => make_button(img_layer_container, 'ist', inst_image.button_name))



    make_button(cell_container, 'ist', 'CELL')
    make_button(trx_container, 'ist', 'TRX')

    img_container.appendChild(img_layer_container)

    ini_slider('cell')
    cell_container.appendChild(cell_slider_container)
    cell_slider_container.appendChild(cell_slider)

    ini_slider('trx')
    trx_container.appendChild(trx_slider_container)
    trx_slider_container.appendChild(trx_slider) 

    ui_container.appendChild(ctrl_container)

    ctrl_container.appendChild(img_container) 
    ctrl_container.appendChild(cell_container) 
    ctrl_container.appendChild(trx_container) 
    
    return ui_container

}