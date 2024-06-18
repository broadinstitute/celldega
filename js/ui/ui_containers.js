export let ui_container = document.createElement("div")

export const ini_ui_container = () => {
    ui_container.style.display = "flex"
    ui_container.style.flexDirection = "row"
    ui_container.style.border = "1px solid #d3d3d3"    
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

// export let img_slider_container = document.createElement("div");
// export const ini_img_slider_container = () => {
//     img_slider_container.className = "slidecontainer";
//     img_slider_container.style.width = "100%";
//     img_slider_container.style.marginLeft = "5px"
//     img_slider_container.style.marginTop = "5px"
// }

export let tile_slider_container = document.createElement("div");

export const ini_tile_slider_container = () => {
    tile_slider_container.className = "slidecontainer";
    tile_slider_container.style.width = "100%";
    tile_slider_container.style.marginLeft = "5px"
    tile_slider_container.style.marginTop = "5px"
}