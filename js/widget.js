import "./widget.css";
import { landscape } from "./viz/landscape";
import { toy } from "./viz/toy";

import { dropdown, update_dropdown } from "./ui/dropdown";

export const render_landscape = async ({ model, el }) => {

    const token = model.get('token_traitlet')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');    
    const ini_z = model.get('ini_z');    
    const ini_zoom = model.get('ini_zoom');
    const base_url = model.get('base_url')

    // Create and append the visualization.
    let root = document.createElement("div");
    root.style.height = "800px";
    el.appendChild(root); 

    return landscape(
        token, 
        ini_x, 
        ini_y, 
        ini_z,
        ini_zoom, 
        base_url, 
        root
    )

}

export const render_toy = ({ model, el }) => {
    
    const base_url = model.get('base_url')

    const options = ["cluster", "B2M", "CPE", "TTR"];

    update_dropdown(options);

    // Create and append the visualization container
    let root = document.createElement("div");
    root.style.height = "800px";

    el.appendChild(dropdown);
    el.appendChild(root);

    return toy(root, base_url);  // Assuming toy is a function that initializes the visualization
}


  export const render = async ({ model, el }) => {

    const componentType = model.get("component");

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
