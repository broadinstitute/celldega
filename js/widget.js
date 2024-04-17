import "./widget.css";
import { make_landscape } from "./viz/make_landscape";

export const render = async ({ model, el }) => {

    const token = model.get('token_traitlet')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');
    const ini_zoom = model.get('ini_zoom');
    const max_image_zoom = model.get('max_image_zoom')
    const bounce_time = model.get('bounce_time')    
    const base_url = model.get('base_url')

    // Create and append the visualization.
    let root = document.createElement("div");
    root.style.height = "800px";
    el.appendChild(root);

    return make_landscape(
        token, ini_x, ini_y, ini_zoom, max_image_zoom, bounce_time, base_url, root
    )

}

export default { render, make_landscape };
