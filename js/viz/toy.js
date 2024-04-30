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

            console.log('here!!!')
    
            // Redefine the fragment shader using template literals for multi-line text
            shaders.fs = `#version 300 es
            #define SHADER_NAME scatterplot-layer-fragment-shader
            precision highp float;
            in vec4 vFillColor;
            in vec2 unitPosition;
            out vec4 fragColor;
            void main(void) {
                geometry.uv = unitPosition;
                fragColor = vFillColor;
                DECKGL_FILTER_COLOR(fragColor, geometry);
            }`;
    
            return shaders;
        }
    }    

    const tile_url = base_url + 'tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)
    var tile_scatter_data = get_scatter_data(tile_arrow_table)
    var tile_names_array = tile_arrow_table.getChild("name").toArray();

    var tile_cats_array = tile_arrow_table.getChild("cluster").toArray();

    console.log(tile_cats_array)

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
        color_dict[String(geneName)] = hexToRgb(colors[index]);
    });

    let custom_scatter_layer = new CustomScatterplotLayer({
        id: 'tile-layer',
        data: tile_scatter_data,
        getFillColor: (i, d) => {
            var inst_name = tile_cats_array[d.index]
            var inst_color = color_dict[inst_name]
            return [inst_color[0], inst_color[1], inst_color[2], 255]
        },
        filled: true,
        getRadius: 0.5, // 8um: 12 with border
        antialiasing: true,
        pickable: true,
        onClick: d => console.log('Clicked on:', d)
    })

    let layers = [custom_scatter_layer]

    const ini_x = 100
    const ini_y = 100
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