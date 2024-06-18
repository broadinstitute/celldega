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