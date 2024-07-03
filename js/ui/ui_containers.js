import { make_cell_button, make_img_button, make_tile_button, make_trx_button } from "./text_buttons"
import { gene_search } from "./gene_search"
import { make_tile_slider, make_trx_slider } from "./sliders"

export const ini_ui_container = () => {
    const ui_container = document.createElement("div")
    ui_container.style.display = "flex"
    ui_container.style.flexDirection = "row"
    ui_container.style.border = "1px solid #d3d3d3"    
    ui_container.className = "ui_container"
    return ui_container
}

export const ini_ctrl_container = () => {
    let ctrl_container = document.createElement("div")
    ctrl_container.className = "ctrl_container"
    ctrl_container.style.width = "250px"
    ctrl_container.style.margin = "10px"
    return ctrl_container
}

export const ini_img_container = () => {
    const img_container = document.createElement("div")
    img_container.className = 'image_container'
    img_container.style.width = "100%"
    img_container.style.margin = "0px"
    img_container.style.display = "flex"
    img_container.style.flexDirection = "row" 
    return img_container
}

export const ini_tile_container = () => {
    let tile_container = document.createElement("div")
    tile_container.className = 'tile_container'
    tile_container.style.width = "100%"
    tile_container.style.margin = "0px"
    tile_container.style.display = "flex"
    tile_container.style.flexDirection = "row"    

    return tile_container
}

export const ini_tile_slider_container = () => {
    const tile_slider_container = document.createElement("div")
    tile_slider_container.className = "slidecontainer"
    tile_slider_container.style.width = "100%"
    tile_slider_container.style.marginLeft = "5px"
    tile_slider_container.style.marginTop = "5px"
    return tile_slider_container
}

export const make_sst_ui_container = () => {

    // UI elements
    const ui_container = ini_ui_container()
    const ctrl_container = ini_ctrl_container()
    const img_container = ini_img_container()
    const tile_container = ini_tile_container()
    const tile_slider_container = ini_tile_slider_container()

    make_img_button(img_container, 'sst')
    make_tile_button(tile_container)  
    make_tile_slider(tile_slider_container)

    ui_container.appendChild(ctrl_container)
    ui_container.appendChild(gene_search)    

    // this needs to be done after making the button
    tile_container.appendChild(tile_slider_container)

    ctrl_container.appendChild(img_container) 
    ctrl_container.appendChild(tile_container)             

    return ui_container

}

export const make_ist_ui_container = () => {

    const ui_container = ini_ui_container()
    const ctrl_container = ini_ctrl_container()
    const img_container = ini_img_container()
    const tile_slider_container = ini_tile_slider_container()

    make_img_button(img_container, 'ist')
    make_cell_button(img_container, 'ist')
    make_trx_button(img_container, 'ist')
    make_trx_slider(tile_slider_container) 

    ui_container.appendChild(ctrl_container)
    ctrl_container.appendChild(img_container) 
    ctrl_container.appendChild(tile_slider_container)

    return ui_container

}