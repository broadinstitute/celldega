import { Deck, TileLayer, BitmapLayer, OrthographicView } from 'deck.gl';
import * as mathGl from 'math.gl';
import { visibleTiles } from "../vector_tile/visibleTiles.js";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { debounce } from "../utils/debounce.js";
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { create_get_tile_data } from "../deck-gl/create_get_tile_data.js";
import { create_render_tile_sublayers } from "../deck-gl/create_render_tile_sublayer.js";
import { path_layer, update_path_layer } from "../deck-gl/path_layer.js";
import { make_cell_layer } from "../deck-gl/make_cell_layer.js";
import { set_options } from '../global_variables/fetch_options.js';
import { trx_layer, update_trx_layer } from '../deck-gl/trx_layer.js';
import { cell_names_array, set_cell_names_array } from '../global_variables/cell_names_array.js';   
import { make_tooltip } from '../deck-gl/make_tooltip.js';
import { landscape_parameters, set_landscape_parameters } from '../global_variables/landscape_parameters.js';
import { dimensions, set_dimensions } from '../global_variables/image_dimensions.js';
import { set_color_dict } from '../global_variables/color_dict.js';
import { layers, update_layers } from '../deck-gl/layers.js';
// import { calc_viewport } from '../deck-gl/calc_viewport.js';

export const landscape = async (
    token, ini_x, ini_y, ini_zoom, bounce_time, base_url, root
) => {

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
                tile_layer_1, 
                tile_layer_2, 
                path_layer, 
                cell_layer, 
                trx_layer]

            update_layers(new_layers)            

        } else {

            new_layers = [tile_layer_1, tile_layer_2, cell_layer]
            update_layers(new_layers)

        }

        deck.setProps({layers});
    }

    var options = set_options(token)


    const imgage_name_for_dim = 'dapi'

    await set_dimensions(base_url, imgage_name_for_dim )
    await set_landscape_parameters(base_url)

    const max_pyramid_zoom = landscape_parameters.max_pyramid_zoom

    const image_name_1 = 'dapi'
    const color_1 = [0, 255, 0]
    const tile_layer_1 = new TileLayer({
        id: 'tile_layer_1',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(base_url, image_name_1, max_pyramid_zoom, options),
        renderSubLayers: create_render_tile_sublayers(dimensions, color_1)
    });    

    const image_name_2 = 'cellbound' 
    const color_2 = [255, 0, 0]
    const tile_layer_2 = new TileLayer({
        id: 'tile_layer_2',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(base_url, image_name_2, max_pyramid_zoom, options),
        renderSubLayers: create_render_tile_sublayers(dimensions, color_2)
    });

    const tileSize = 1000;
    const max_tiles_to_view = 15

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_color_dict(base_url)

    set_cell_names_array(cell_arrow_table)

    const cell_layer = make_cell_layer(cell_scatter_data, cell_names_array)

    update_layers([tile_layer_1, tile_layer_2, cell_layer])

    const initial_view_state = {
        target: [ini_x, ini_y, 0], 
        zoom: ini_zoom
    }

    const view = new OrthographicView({id: 'ortho'})

    const debounced_calc_viewport = debounce(calc_viewport, bounce_time);

    const on_view_state_change = ({viewState}) => {
        debounced_calc_viewport(viewState)
        return viewState
    }        

    let deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: initial_view_state,
        views: [view],
        layers: layers,
        onViewStateChange: on_view_state_change,
        getTooltip: make_tooltip,
    });    

    return () => deck.finalize();        

}