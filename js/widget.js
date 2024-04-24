import "./widget.css";
import { landscape } from "./viz/landscape";

export const render_landscape = async ({ model, el }) => {

    const token = model.get('token_traitlet')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');
    const ini_zoom = model.get('ini_zoom');
    // const max_image_zoom = model.get('max_image_zoom')
    const bounce_time = model.get('bounce_time')    
    const base_url = model.get('base_url')

    // Create and append the visualization.
    let root = document.createElement("div");
    root.style.height = "800px";
    el.appendChild(root);

    return landscape(
        token, 
        ini_x, 
        ini_y, 
        ini_zoom, 
        // max_image_zoom, 
        bounce_time, 
        base_url, 
        root
    )

}

export const render_toy = ({ model, el }) => {
    let button = document.createElement("button");
    button.innerHTML = `count is ${model.get("value")}`;
    button.addEventListener("click", () => {
      model.set("value", model.get("value") + 1);
      model.save_changes();
    });
    model.on("change:value", () => {
      button.innerHTML = `count is ${model.get("value")}`;
    });
    el.appendChild(button);
  }

  export const render = async ({ model, el }) => {

    console.log('trying to make generic render function')
    console.log(model)
    const componentType = model.get("component");

    console.log('componentType', componentType)
    // const root = document.createElement("div");
    // root.style.height = "800px";
    // el.appendChild(root);

    switch (componentType) {
        case "Landscape":
            render_landscape({ model, el });
            break;
        case "Toy":
            render_toy({ model, el });
            break;
        default:
            throw new Error(`Unknown component type: ${componentType}`);
    }
};
  

export default { render, landscape };
