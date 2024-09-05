import { SolidPolygonLayer } from 'deck.gl';


// Function to create a background layer
export const ini_background_layer = (viz_state) => {

  const background_color = [0, 0, 0, 255]
  const { width, height } = viz_state.dimensions;
  let background_layer = new SolidPolygonLayer({
    id: 'background-layer',
    data: [{
      // Define the polygon that covers the entire visible area
      polygon: [[0, 0], [width, 0], [width, height], [0, height]],
      // Optionally, you can add more attributes here if needed
    }],
    getPolygon: d => d.polygon,
    getFillColor: background_color,
    pickable: false
  })

  return background_layer

}

export const toggle_background_layer_visibility = (layers_obj, visible) => {
  layers_obj.background_layer = layers_obj.background_layer.clone({
      visible: visible,
  })
}
