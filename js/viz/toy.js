import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { Deck, ScatterplotLayer } from 'deck.gl';
import { options, set_options } from '../global_variables/fetch_options.js';
import { views, update_views } from '../deck-gl/views.js';
import { initial_view_state, set_initial_view_state } from "../deck-gl/initial_view_state.js";
import { hexToRgb } from '../utils/hexToRgb.js'

export const toy = async ( root, base_url ) => {


    set_options('')

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


    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)
    var tile_scatter_data = get_scatter_data(tile_arrow_table)

    // let tile_layer = new ScatterplotLayer({
    //     id: 'tile-layer',
    //     data: tile_scatter_data,
    //     getRadius: 5.0,
    //     pickable: true,
    //     getColor: [0, 0, 255, 240],
    // })

    // const response = await fetch(base_url + 'meta_tile.json')
    // const meta_tile = await response.json()
    // console.log(meta_tile)    

    let color_dict = {}

    const df_colors_url = base_url + `/df_colors.parquet`;
    var df_colors = await get_arrow_table(df_colors_url, options.fetch)

    let names = [];
    let colors = [];

    const nameColumn = df_colors.getChild('__index_level_0__');
    const colorColumn = df_colors.getChild('color');

    if (nameColumn && colorColumn) {
        names = nameColumn.toArray();
        colors = colorColumn.toArray();
    }    

    names.forEach((geneName, index) => {
        color_dict[geneName] = hexToRgb(colors[index]);
    });

    let custom_scatter_layer = new CustomScatterplotLayer({
        // data: [{ position: [-122.45, 37.8], color: [0, 0, 255], radius: 100}],
        data: tile_scatter_data,
        getFillColor: [255, 0, 0, 255],
        // getRadius: d => d.radius,
        // getRadius: 24.0, // 16
        getRadius: 12.0, // 8um
        // getRadius: 3.0, // 2um

        pickable: true,
        onClick: d => console.log('Clicked on:', d)
    })

    let layers = [custom_scatter_layer]

    const ini_x = 10000
    const ini_y = 10000
    const ini_z = 0
    const ini_zoom = 0

    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)    
    update_views()

    let deck = new Deck({
        parent: root,
        controller: true,
        initialViewState: initial_view_state,
        layers: layers,    
        views: views
    });
    return () => deck.finalize();  

}