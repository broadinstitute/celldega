import { fetch_all_tables } from '../../read_parquet/fetch_all_tables.js'
import { get_polygon_data } from '../../read_parquet/get_polygon_data.js'
import { concatenate_polygon_data } from '../concatenate_functions.js'
import { extractPolygonPaths } from './extractPolygonPaths.js'

export const grab_cell_tiles_in_view = async (base_url, tiles_in_view, options) => {

    const tile_cell_urls = tiles_in_view.map(tile => {
        return `${base_url}/cell_segmentation/cell_tile_${tile.tileX}_${tile.tileY}.parquet`;
    });

    // var tile_cell_tables = await fetch_all_tables(cache_cell, tile_cell_urls, options)
    var tile_cell_tables = await fetch_all_tables('cell', tile_cell_urls, options)

    var polygon_datas = tile_cell_tables.map(x => get_polygon_data(x))

    var polygon_data = concatenate_polygon_data(polygon_datas);

    var polygonPathsConcat = extractPolygonPaths(polygon_data)

    return polygonPathsConcat
}