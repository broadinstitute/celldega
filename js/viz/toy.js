import { get_arrow_table } from "../read_parquet/get_arrow_table";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { Deck, ScatterplotLayer } from 'deck.gl';
import { options, set_options } from '../global_variables/fetch_options.js';
import { views, update_views } from '../deck-gl/views.js';
import { initial_view_state, set_initial_view_state } from "../deck-gl/initial_view_state.js";
import { hexToRgb } from '../utils/hexToRgb.js'

export const toy = async ( root, base_url ) => {


    set_options('')

    // class CustomScatterplotLayer extends ScatterplotLayer {
    //     getShaders() {
    //         // Get the default shaders from the ScatterplotLayer
    //         const shaders = super.getShaders();

    //         console.log(shaders)
        
    //         // Modify the fragment shader
    //         shaders.fs = shaders.fs.replace(
    //         `float distToCenter = length(unitPosition) * outerRadiusPixels;`,
    //         `// No change to distToCenter needed, but we change the discard logic
    //             float distToCenter = max(abs(unitPosition.x), abs(unitPosition.y));`
    //         ).replace(
    //         `if (inCircle == 0.0) { discard; }`,
    //         `if (distToCenter > outerRadiusPixels) { discard; } // Change to square boundaries`
    //         );
        
    //         return shaders;
    //     }
    // }

    // // appears to be working
    // /////////////////////////////////
    // class CustomScatterplotLayer extends ScatterplotLayer {
    //     getShaders() {
    //         // Get the default shaders from the ScatterplotLayer
    //         const shaders = super.getShaders();

    //         console.log('here!!!')
    
    //         // Redefine the fragment shader using template literals for multi-line text
    //         shaders.fs = `#version 300 es
    //         #define SHADER_NAME scatterplot-layer-fragment-shader
    //         precision highp float;
    //         uniform bool filled;
    //         uniform float stroked;
    //         uniform bool antialiasing;
    //         in vec4 vFillColor;
    //         in vec4 vLineColor;
    //         in vec2 unitPosition;
    //         in float innerUnitRadius;
    //         in float outerRadiusPixels;
    //         out vec4 fragColor;
    //         void main(void) {
    //             geometry.uv = unitPosition;
    //             float distToCenter = max(abs(unitPosition.x), abs(unitPosition.y));
    //             float inCircle = antialiasing ?
    //                 smoothedge(distToCenter, outerRadiusPixels) :
    //                 step(distToCenter, outerRadiusPixels);
    //             if (inCircle == 0.0) {
    //                 discard;
    //             }
    //             if (stroked > 0.5) {
    //                 float isLine = antialiasing ?
    //                     smoothedge(innerUnitRadius * outerRadiusPixels, distToCenter) :
    //                     step(innerUnitRadius * outerRadiusPixels, distToCenter);
    //                 if (filled) {
    //                     fragColor = mix(vFillColor, vLineColor, isLine);
    //                 } else {
    //                     if (isLine == 0.0) {
    //                         discard;
    //                     }
    //                     fragColor = vec4(vLineColor.rgb, vLineColor.a * isLine);
    //                 }
    //             } else if (!filled) {
    //                 discard;
    //             } else {
    //                 fragColor = vFillColor;
    //             }
    //             fragColor.a *= inCircle;
    //             DECKGL_FILTER_COLOR(fragColor, geometry);
    //         }`;
    
    //         return shaders;
    //     }
    // }


    class CustomScatterplotLayer extends ScatterplotLayer {
        getShaders() {
            // Get the default shaders from the ScatterplotLayer
            const shaders = super.getShaders();

            console.log('here!!!')
    
            // Redefine the fragment shader using template literals for multi-line text
            shaders.fs = `#version 300 es
            #define SHADER_NAME scatterplot-layer-fragment-shader
            precision highp float;
            uniform bool filled;
            uniform float stroked;
            uniform bool antialiasing;
            in vec4 vFillColor;
            in vec4 vLineColor;
            in vec2 unitPosition;
            in float innerUnitRadius;
            in float outerRadiusPixels;
            out vec4 fragColor;
            void main(void) {
                geometry.uv = unitPosition;
                fragColor = vFillColor;
                DECKGL_FILTER_COLOR(fragColor, geometry);
            }`;
    
            return shaders;
        }
    }    

    // class CustomScatterplotLayer extends ScatterplotLayer {
    //     getShaders() {
    //         const shaders = super.getShaders();
    //         shaders.fs = `#version 300 es
    //         #define SHADER_NAME custom-scatterplot-layer-fragment-shader
    //         precision highp float;
    
    //         uniform bool filled;
    //         uniform vec4 vFillColor;
    //         uniform vec4 vLineColor;
    //         in vec2 unitPosition;
    //         out vec4 fragColor;
    
    //         void main(void) {
    //             fragColor = filled ? vFillColor : vLineColor;
    
    //             // Apply the picking filter which is essential for interaction
    //             fragColor = picking_filterPickingColor(fragColor);
    //         }`;
    
    //         return shaders;
    //     }
    // }
    
    

    console.log(base_url)

    const tile_url = base_url + 'tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)
    var tile_scatter_data = get_scatter_data(tile_arrow_table)
    var tile_names_array = tile_arrow_table.getChild("name").toArray();

    var tile_cats_array = tile_arrow_table.getChild("cluster").toArray();

    console.log(tile_cats_array)

    // console.log(tile_names_array)
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
        color_dict[String(geneName)] = hexToRgb(colors[index]);
    });

    console.log(color_dict)

    let custom_scatter_layer = new CustomScatterplotLayer({
        // data: [{ position: [-122.45, 37.8], color: [0, 0, 255], radius: 100}],
        id: 'tile-layer',
        data: tile_scatter_data,
        // getFillColor: [255, 0, 0, 255],
        getFillColor: (i, d) => {

            var inst_name = tile_cats_array[d.index]
            var inst_color = color_dict[inst_name]
            // console.log(d.index, inst_name, inst_color)
            // console.log(inst_color)
            return [inst_color[0], inst_color[1], inst_color[2], 255]
            // return [255, 0, 0, 255]
        },
        // getRadius: d => d.radius,
        // getRadius: 24.0, // 16
        filled: true,
        getRadius: 0.5, // 8um: 12 with border
        antialiasing: true,
        // getRadius: 3.0, // 2um

        pickable: true,
        onClick: d => console.log('Clicked on:', d)
    })

    let layers = [custom_scatter_layer]

    // const ini_x = 10000
    // const ini_y = 10000
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