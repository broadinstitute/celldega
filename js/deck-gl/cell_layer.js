import { ScatterplotLayer } from 'deck.gl'
import { get_arrow_table } from "../read_parquet/get_arrow_table.js"
import { get_scatter_data } from "../read_parquet/get_scatter_data.js"
import { set_color_dict } from '../global_variables/color_dict.js'
import { cell_names_array, set_cell_names_array, set_cell_name_to_index_map } from '../global_variables/cell_names_array.js'
import { options } from '../global_variables/fetch_options.js'
// import { selected_cats } from '../global_variables/selected_cats.js'
import { cat } from '../global_variables/cat.js'
import { cell_exp_array } from '../global_variables/cell_exp_array.js'

// transparent to red
const cell_layer_color = (i, d) => {
    if (cat === 'cluster') {
        // const inst_cat = tile_cats_array[d.index];
        // const opacity = (selected_cats.length === 0 || selected_cats.includes(inst_cat)) ? 255 : 25;
        // return [...color_dict[inst_cat], opacity];

        return [0, 0, 255, 255]
    } else {

        const inst_exp = cell_exp_array[d.index]

        return [255, 0, 0, inst_exp]

    }
}

// // opaque white to red
// /////////////////////////////////////
// const cell_layer_color = (i, d) => {
//     if (cat === 'cluster') {
//         return [0, 0, 255, 255]; // Use blue for cluster category
//     } else {
//         const inst_exp = cell_exp_array[d.index];

//         // Interpolate between white and red based on the expression value
//         const red = Math.floor((inst_exp / 255) * 255);
//         const green = Math.floor((inst_exp / 255) * 255); // To blend from white to red, green and blue components also change
//         const blue = Math.floor((inst_exp / 255) * 255);  // To blend from white to red, green and blue components also change

//         return [255, 255 - green, 255 - blue, 255]; // Full opacity
//     }
// };

// // Function to generate cell layer color
// const cell_layer_color = (i, d) => {

//     const color_scheme = 'black_to_red'
//     if (cat === 'cluster') {
//         return [0, 0, 255, 255]; // Use blue for cluster category
//     } else {
//         const inst_exp = cell_exp_array[d.index];
//         const red = Math.floor((inst_exp / 255) * 255);
//         let color;

//         if (color_scheme === 'white_to_red') {
//             const green = 255 - red; // Green decreases as red increases
//             const blue = 255 - red; // Blue decreases as red increases
//             // const opacity = inst_exp > 50 ? 255 : 0; // Full opacity for expression > 50
//             color = [255, green, blue, 255]; // Full opacity
//         } else if (color_scheme === 'black_to_red') {
//             // const opacity = inst_exp > 50 ? 255 : 0; // Full opacity for expression > 50
//             color = [red, 0, 0, 255]; // From black to red with full opacity
//         }

//         return color;
//     }
// };


// // blue to white to red
// const cell_layer_color = (i, d) => {
//     if (cat === 'cluster') {
//         return [0, 0, 255, 255]; // Use blue for cluster category
//     } else {
//         const inst_exp = cell_exp_array[d.index];

//         // Define the three colors
//         const lowColor = [0, 0, 255]; // Blue
//         const midColor = [255, 255, 255]; // White
//         const highColor = [255, 0, 0]; // Red

//         // Determine the interpolation factor (between 0 and 1)
//         const factor = inst_exp / 255;

//         let color;

//         if (factor < 0.5) {
//             // Interpolate between lowColor and midColor
//             const interpFactor = factor * 2;
//             color = [
//                 Math.floor(lowColor[0] + interpFactor * (midColor[0] - lowColor[0])),
//                 Math.floor(lowColor[1] + interpFactor * (midColor[1] - lowColor[1])),
//                 Math.floor(lowColor[2] + interpFactor * (midColor[2] - lowColor[2]))
//             ];
//         } else {
//             // Interpolate between midColor and highColor
//             const interpFactor = (factor - 0.5) * 2;
//             color = [
//                 Math.floor(midColor[0] + interpFactor * (highColor[0] - midColor[0])),
//                 Math.floor(midColor[1] + interpFactor * (highColor[1] - midColor[1])),
//                 Math.floor(midColor[2] + interpFactor * (highColor[2] - midColor[2]))
//             ];
//         }

//         return [...color, 255]; // Full opacity
//     }
// };


export let cell_layer = new ScatterplotLayer({
    id: 'cell-layer',
    radiusMinPixels: 1,
    getRadius: 5.0,
    pickable: true,
    getColor: cell_layer_color,
})


export const update_cell_layer = async (base_url) => {

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_color_dict(base_url)

    set_cell_names_array(cell_arrow_table)
    set_cell_name_to_index_map()

    cell_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...cell_layer.props,
        data: cell_scatter_data,
        onClick: info => {
            console.log('click!!')
            console.log(info.index)
            console.log(cell_names_array[info.index])
        },
    });
}

export const toggle_cell_layer_visibility = (visible) => {
    cell_layer = cell_layer.clone({
        visible: visible,
    });
}

export const update_cell_layer_radius = (radius) => {
    cell_layer = cell_layer.clone({
        getRadius: radius,
    });
}

export const update_cell_layer_id = (new_cat) => {

    console.log('update cell layer id')
    cell_layer = cell_layer.clone({
        id: 'cell-layer-' + new_cat,
    });
}