import { Deck, ScatterplotLayer, TileLayer, BitmapLayer, OrthographicView } from 'deck.gl';
import * as mathGl from 'math.gl';

import { visibleTiles } from "../vector_tile/visibleTiles.js";
import { concatenate_arrow_tables } from "../vector_tile/concatenate_functions.js";
import { fetch_all_tables } from "../read_parquet/fetch_all_tables.js";
import { get_scatter_data } from "../read_parquet/get_scatter_data.js";
import { debounce } from "../utils/debounce.js";
import { hexToRgb } from "../utils/hexToRgb.js";
import { get_arrow_table } from "../read_parquet/get_arrow_table.js";
import { create_get_tile_data } from "../deck-gl/create_get_tile_data.js";
import { create_render_tile_sublayers } from "../deck-gl/create_render_tile_sublayer.js";
import { make_polygon_layer } from "../deck-gl/make_polygon_layer.js";
import { make_polygon_layer_new } from "../deck-gl/make_polygon_layer_new.js";
import { get_image_dimensions } from "../image_tile/get_image_dimensions.js";
import { make_cell_layer } from "../deck-gl/make_cell_layer.js";

console.log('testing rebuild for front-end')


export const make_landscape = async (
    token, ini_x, ini_y, ini_zoom, max_image_zoom, bounce_time, base_url, root
) => {

    console.log('moved the bulk of the code to make_landscape')

    const cache_trx = new Map();
    const cache_cell = new Map();
    
    let trx_names_array = [];

    const grab_trx_tiles_in_view = async (tiles_in_view, options) => {

      const tile_trx_urls = tiles_in_view.map(tile => {
        return `${base_url}/real_transcript_tiles_mosaic/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
      });
    
      var tile_trx_tables = await fetch_all_tables(cache_trx, tile_trx_urls, options)
      var trx_arrow_table = concatenate_arrow_tables(tile_trx_tables)
      trx_names_array = trx_arrow_table.getChild("name").toArray();
      var trx_scatter_data = get_scatter_data(trx_arrow_table)
    
      return trx_scatter_data
    }

    const make_trx_layer_new = async (
        tiles_in_view, 
        options, 
        base_url, 
        cache_trx, 
        trx_names_array
    ) => {

        let trx_scatter_data = grab_trx_tiles_in_view(
            tiles_in_view, 
            options, 
            base_url, 
            cache_trx, 
            trx_names_array
        )

        const trx_layer_new = new ScatterplotLayer({
            // Re-use existing layer props
            ...trx_layer.props,
            data: trx_scatter_data,
        });

        return trx_layer_new
            
    }
  
    const calc_viewport = async ({ height, width, zoom, target }, options) => {

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

            const trx_layer_new = await make_trx_layer_new(
                tiles_in_view, 
                options, 
                base_url, 
                cache_trx, 
                trx_names_array
            )

            // cell tiles
            ////////////////////////////////
            const polygon_layer_new = await make_polygon_layer_new(
                tiles_in_view, 
                options, 
                base_url, 
                cache_cell, 
                polygon_layer
            )

            // update layer
            deck.setProps({
                layers: [
                    tile_layer_2, 
                    tile_layer, 
                    polygon_layer_new, 
                    cell_layer, 
                    trx_layer_new]
            });

        } else {
            deck.setProps({
                layers: [tile_layer_2, tile_layer, cell_layer]
            });
        }
    };

    const make_tooltip = (info) => {

        let inst_name

        if (info.index === -1 || !info.layer) return null;

        if (info.layer.id === 'cell-layer'){
            inst_name = cell_names_array[info.index]
        } else if (info.layer.id === 'trx-layer') {
            inst_name = trx_names_array[info.index]
        }

        return {
            html: `<div>${inst_name}</div?`,
        };

    }
      
    // authorization token for bucket
    const options = ({
        fetch: {
            headers: {
            'Authorization': `Bearer ${token}` // Use the token in the Authorization header
            }
        }
    })

    const image_name = 'cellbound' 

    const dimensions = await get_image_dimensions(base_url, image_name, options)

    const tile_layer = new TileLayer({
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: create_get_tile_data(base_url, image_name, max_image_zoom, options),
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
        getTileData: create_get_tile_data(base_url, image_name_2, max_image_zoom, options),
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

    const cell_url = base_url + `/real_cells_mosaic.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    const meta_gene_url = base_url + `/meta_gene.parquet`;
    var meta_gene = await get_arrow_table(meta_gene_url, options.fetch)

    let geneNames = [];
    let colors = [];

    const geneNameColumn = meta_gene.getChild('__index_level_0__');
    const colorColumn = meta_gene.getChild('color');

    if (geneNameColumn && colorColumn) {
        // If the table is large, consider a more efficient way to handle data extraction
        geneNames = geneNameColumn.toArray();
        colors = colorColumn.toArray();
    }

    let color_dict = {};

    geneNames.forEach((geneName, index) => {
        color_dict[geneName] = hexToRgb(colors[index]);
    });

    const cell_names_array = cell_arrow_table.getChild("name").toArray();

    const cell_layer = make_cell_layer(cell_scatter_data, cell_names_array)

    // mutable transcript data is initialized as an empty array
    var trx_data = []

    const trx_layer = new ScatterplotLayer({
        id: 'trx-layer',
        data: trx_data,
        getRadius: 0.5,
        pickable: true,
        getColor: (i, d) => {
            var inst_gene = trx_names_array[d.index]
            var inst_color = color_dict[inst_gene]
            return [inst_color[0], inst_color[1], inst_color[2], 255]
        },
    });       

    const polygon_layer = make_polygon_layer()    

    let deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: {target: [ini_x, ini_y, 0], zoom: ini_zoom},
        views: [new OrthographicView({id: 'ortho'})],
        layers: [tile_layer_2, tile_layer, cell_layer],
        onViewStateChange: ({viewState}) => {
            debounced_calc_viewport(viewState, options)
            return viewState
        },
        getTooltip: make_tooltip,
    });    

    return () => deck.finalize();        


}