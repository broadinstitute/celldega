import { make_img_button, make_tile_button } from "./text_buttons"
import { gene_search } from "./gene_search"
import { make_tile_slider } from "./sliders"

export let ui_container = document.createElement("div")

export const ini_ui_container = () => {
    ui_container.style.display = "flex"
    ui_container.style.flexDirection = "row"
    ui_container.style.border = "1px solid #d3d3d3"    
    ui_container.className = "ui_container"
}

export let ctrl_container = document.createElement("div")

export const ini_ctrl_container = () => {
    ctrl_container.className = "ctrl_container"
    ctrl_container.style.width = "250px"
    ctrl_container.style.margin = "10px"
}

export let img_container = document.createElement("div")

export const ini_img_container = () => {
    img_container.className = 'image_container'
    img_container.style.width = "100%"
    img_container.style.margin = "0px"
    img_container.style.display = "flex"
    img_container.style.flexDirection = "row" 
}

export let tile_container = document.createElement("div")

export const ini_tile_container = () => {
    tile_container.className = 'tile_container'
    tile_container.style.width = "100%"
    tile_container.style.margin = "0px"
    tile_container.style.display = "flex"
    tile_container.style.flexDirection = "row"    
}

export let tile_slider_container = document.createElement("div");

export const ini_tile_slider_container = () => {
    tile_slider_container.className = "slidecontainer";
    tile_slider_container.style.width = "100%";
    tile_slider_container.style.marginLeft = "5px"
    tile_slider_container.style.marginTop = "5px"
}

export const make_sst_ui_container = () => {

    // UI elements
    ini_ui_container()
    ini_ctrl_container()
    ini_img_container()
    ini_tile_container()
    ini_tile_slider_container()

    make_img_button(img_container, 'sst')
    make_tile_button(tile_container)

    make_tile_slider(tile_slider_container)    

    // this needs to be done after making the button
    tile_container.appendChild(tile_slider_container)

    ctrl_container.appendChild(img_container) 
    ctrl_container.appendChild(tile_container)         

    ui_container.appendChild(ctrl_container)
    ui_container.appendChild(gene_search)    

}

export const make_ist_ui_container = () => {

    ini_ui_container()
    ini_ctrl_container()
    ini_img_container()
    // ini_tile_container()


    make_img_button(img_container, 'ist')
    // make_tile_button(tile_container)    

    ctrl_container.appendChild(img_container) 
    // ctrl_container.appendChild(tile_container)         

    ui_container.appendChild(ctrl_container)
    // ui_container.appendChild(gene_search)        

}