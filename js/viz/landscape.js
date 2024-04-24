import { Deck, TileLayer, BitmapLayer, OrthographicView } from 'deck.gl';
import * as mathGl from 'math.gl';

import { visibleTiles } from "../vector_tile/visibleTiles.js";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { debounce } from "../utils/debounce.js";
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { create_get_tile_data } from "../deck-gl/create_get_tile_data.js";
import { create_render_tile_sublayers } from "../deck-gl/create_render_tile_sublayer.js";
import { make_polygon_layer } from "../deck-gl/make_polygon_layer.js";
import { make_polygon_layer_new } from "../deck-gl/make_polygon_layer_new.js";
import { make_cell_layer } from "../deck-gl/make_cell_layer.js";
import { set_options } from '../global_variables/fetch_options.js';
import { trx_layer, update_trx_layer } from '../deck-gl/trx_layer.js';
import { cell_names_array, set_cell_names_array } from '../global_variables/cell_names_array.js';   
import { make_tooltip } from '../deck-gl/make_tooltip.js';
import { landscape_parameters, set_landscape_parameters } from '../global_variables/landscape_parameters.js';
import { dimensions, set_dimensions } from '../global_variables/image_dimensions.js';
import { set_color_dict } from '../global_variables/color_dict.js';


console.log('testing rebuild for front-end')


export const landscape = async (
    token, ini_x, ini_y, ini_zoom, bounce_time, base_url, root
) => {

    console.log('moved tooltip')
    const calc_viewport = async ({ height, width, zoom, target }) => {

        const zoomFactor = Math.pow(2, zoom);
        const [targetX, targetY] = target;
        const halfWidthZoomed = width / (2 * zoomFactor);
        const halfHeightZoomed = height / (2 * zoomFactor);

        const minX = targetX - halfWidthZoomed;
        const maxX = targetX + halfWidthZoomed;
        const minY = targetY - halfHeightZoomed;
        const maxY = targetY + halfHeightZoomed;

        const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tileSize);

        var num_tiles_to_viz = tiles_in_view.length

        if (num_tiles_to_viz < max_tiles_to_view) {

            await update_trx_layer(
                base_url,
                tiles_in_view, 
            )

            const polygon_layer_new = await make_polygon_layer_new(
                base_url, 
                tiles_in_view, 
                polygon_layer
            )

            deck.setProps({
                layers: [
                    tile_layer_2, 
                    tile_layer, 
                    polygon_layer_new, 
                    cell_layer, 
                    trx_layer]
            });

        } else {
            deck.setProps({
                layers: [tile_layer_2, tile_layer, cell_layer]
            });
        }
    };

    var options = set_options(token)

    const image_name = 'cellbound' 

    const imgage_name_for_dim = 'dapi'

    // const dimensions = await get_image_dimensions(base_url, imgage_name_for_dim, options)
    await set_dimensions(base_url, imgage_name_for_dim )

    await set_landscape_parameters(base_url)

    const max_pyramid_zoom = landscape_parameters.max_pyramid_zoom

    const tile_layer = new TileLayer({
        id: 'tile_layer',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(base_url, image_name, max_pyramid_zoom, options),
        renderSubLayers: create_render_tile_sublayers(dimensions)
    });

    const image_name_2 = 'dapi'

    const tile_layer_2 = new TileLayer({
        id: 'tile_layer_2',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(base_url, image_name_2, max_pyramid_zoom, options),
        renderSubLayers: props => {
            const {
                bbox: {left, bottom, right, top}
            } = props.tile;
            const {width, height} = dimensions;

            return new BitmapLayer(props, {
                data: null,
                image: props.data,
                bounds: [
                    mathGl.clamp(left, 0, width),
                    mathGl.clamp(bottom, 0, height),
                    mathGl.clamp(right, 0, width),
                    mathGl.clamp(top, 0, height)
                ]
            });
        },
    });

    const tileSize = 1000;
    const max_tiles_to_view = 15

    const debounced_calc_viewport = debounce(calc_viewport, bounce_time);

    const cell_url = base_url + `/cell_metadata.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    await set_color_dict(base_url)

    set_cell_names_array(cell_arrow_table)

    const cell_layer = make_cell_layer(cell_scatter_data, cell_names_array)

    const polygon_layer = make_polygon_layer()    

    let deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: {target: [ini_x, ini_y, 0], zoom: ini_zoom},
        views: [new OrthographicView({id: 'ortho'})],
        layers: [tile_layer_2, tile_layer, cell_layer],
        onViewStateChange: ({viewState}) => {
            debounced_calc_viewport(viewState)
            return viewState
        },
        getTooltip: make_tooltip,
    });    

    return () => deck.finalize();        


}