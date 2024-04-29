import "./widget.css";
import { landscape } from "./viz/landscape";


import { Deck } from 'deck.gl';
import { ScatterplotLayer } from 'deck.gl';

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

    console.log(Deck.VERSION)

    class CustomScatterplotLayer extends ScatterplotLayer {
        getShaders() {
          // Get the default shaders from the ScatterplotLayer
          const shaders = super.getShaders();
      
          // Modify the fragment shader
          shaders.fs = shaders.fs.replace(
            `float distToCenter = length(unitPosition) * outerRadiusPixels;`,
            `// No change to distToCenter needed, but we change the discard logic
             float distToCenter = max(abs(unitPosition.x), abs(unitPosition.y));`
          ).replace(
            `if (inCircle == 0.0) { discard; }`,
            `if (distToCenter > outerRadiusPixels) { discard; } // Change to square boundaries`
          );
      
          return shaders;
        }
      }    

    let root = document.createElement("div");
    root.style.height = "800px";
    let deck = new Deck({
    parent: root,
    controller: true,
    initialViewState: { longitude: -122.45, latitude: 37.8, zoom: 15 },
    // layers: [
    //     new ScatterplotLayer({
    //         data: [{ position: [-122.45, 37.8], color: [255, 0, 0], radius: 100}],
    //         getFillColor: d => d.color,
    //         getRadius: d => d.radius,
    //         pickable: true,
    //         onClick: d => console.log('hi hi hi', d)
    //     })
    // ],
    layers: [
        new CustomScatterplotLayer({
          data: [{ position: [-122.45, 37.8], color: [255, 0, 0], radius: 100}],
          getFillColor: d => d.color,
          getRadius: d => d.radius,
          pickable: true,
          onClick: d => console.log('Clicked on:', d)
        })
      ],    
    });
    el.appendChild(root);
    return () => deck.finalize();  

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
