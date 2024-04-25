import { Deck } from 'deck.gl';
import { visibleTiles } from "../vector_tile/visibleTiles.js";
// import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { debounce } from "../utils/debounce.js";
// import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { path_layer, update_path_layer } from "../deck-gl/path_layer.js";
import { cell_layer, update_cell_layer } from "../deck-gl/cell_layer.js";
import { set_options } from '../global_variables/fetch_options.js';
import { trx_layer, update_trx_layer } from '../deck-gl/trx_layer.js';
// import { cell_names_array, set_cell_names_array } from '../global_variables/cell_names_array.js'
import { make_tooltip } from '../deck-gl/make_tooltip.js';
import { set_landscape_parameters } from '../global_variables/landscape_parameters.js';
import { set_dimensions } from '../global_variables/image_dimensions.js';
// import { set_color_dict } from '../global_variables/color_dict.js';
import { layers, update_layers } from '../deck-gl/layers.js';
import { image_layers, update_image_layers } from '../deck-gl/image_layers.js';
import { set_global_base_url } from '../global_variables/global_base_url.js';
import { views, update_views } from '../deck-gl/views.js';

// import { calc_viewport } from '../deck-gl/calc_viewport.js';

export const landscape = async (
    token, ini_x, ini_y, ini_zoom, bounce_time, base_url, root
) => {

    set_global_base_url(base_url)

    const calc_viewport = async ({ height, width, zoom, target }) => {

        let new_layers = []

        const zoomFactor = Math.pow(2, zoom);
        const [targetX, targetY] = target;
        const halfWidthZoomed = width / (2 * zoomFactor);
        const halfHeightZoomed = height / (2 * zoomFactor);

        const minX = targetX - halfWidthZoomed;
        const maxX = targetX + halfWidthZoomed;
        const minY = targetY - halfHeightZoomed;
        const maxY = targetY + halfHeightZoomed;

        const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tileSize);

        if (tiles_in_view.length < max_tiles_to_view) {

            await update_trx_layer(base_url, tiles_in_view)
            await update_path_layer(base_url, tiles_in_view)

            new_layers = [
                ...image_layers, 
                path_layer, 
                cell_layer, 
                trx_layer]

            update_layers(new_layers)            

        } else {

            new_layers = [...image_layers, cell_layer]
            update_layers(new_layers)

        }

        deck.setProps({layers});
    }

    var options = set_options(token)


    const imgage_name_for_dim = 'dapi'

    await set_dimensions(base_url, imgage_name_for_dim )
    await set_landscape_parameters(base_url)

    const image_info = [
        { 
            name: 'dapi', 
            color: [0, 255, 0]
        },
        {   
            name: 'cellbound', 
            color: [255, 0, 0]
        }
    ]

    await update_image_layers(base_url, image_info)

    const tileSize = 1000;
    const max_tiles_to_view = 15

    await update_cell_layer(base_url)

    update_layers([...image_layers, cell_layer])

    const initial_view_state = {
        target: [ini_x, ini_y, 0], 
        zoom: ini_zoom
    }

    update_views()

    const debounced_calc_viewport = debounce(calc_viewport, bounce_time);

    const on_view_state_change = ({viewState}) => {
        debounced_calc_viewport(viewState)
        return viewState
    }        

    let deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        views: views,
        layers: layers,
        onViewStateChange: on_view_state_change,
        getTooltip: make_tooltip,
    });    

    return () => deck.finalize();        

}