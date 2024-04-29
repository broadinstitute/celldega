import { cell_layer, update_cell_layer } from "../deck-gl/cell_layer";
import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { Deck, ScatterplotLayer } from 'deck.gl';

export const toy = async ( root, base_url) => {

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

    console.log(base_url)

    const tile_url = base_url + 'tile_geometries.parquet'
    // await update_cell_layer(base_url)  

    // var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)





    let deck = new Deck({
    parent: root,
    controller: true,
    initialViewState: { longitude: -122.45, latitude: 37.8, zoom: 15 },
    layers: [
        new CustomScatterplotLayer({
        data: [{ position: [-122.45, 37.8], color: [0, 0, 255], radius: 100}],
        getFillColor: d => d.color,
        getRadius: d => d.radius,
        pickable: true,
        onClick: d => console.log('Clicked on:', d)
        })
    ],    
    });
    return () => deck.finalize();  

}