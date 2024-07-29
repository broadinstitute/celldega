import { fetch_all_tables } from '../../read_parquet/fetch_all_tables.js'
import { get_polygon_data } from '../../read_parquet/get_polygon_data.js'
import { concatenate_polygon_data } from '../concatenate_functions.js'
import { extractPolygonPaths } from './extractPolygonPaths.js'
import { options } from '../../global_variables/fetch_options.js'

export let polygon_cell_names = []

export const grab_cell_tiles_in_view = async (base_url, tiles_in_view) => {

    const tile_cell_urls = tiles_in_view.map(tile => {
        return `${base_url}/cell_segmentation/cell_tile_${tile.tileX}_${tile.tileY}.parquet`;
    });

    var tile_cell_tables_ini = await fetch_all_tables('cell', tile_cell_urls, options)

    var tile_cell_tables = tile_cell_tables_ini.filter(table => table !== null);

    polygon_cell_names = tile_cell_tables.flatMap(table =>
        Array.from(table.getChild('name').toArray())
    )

    var polygon_datas = tile_cell_tables.map(x => get_polygon_data(x))

    var polygon_data = concatenate_polygon_data(polygon_datas);

    var polygonPathsConcat = extractPolygonPaths(polygon_data)

    return polygonPathsConcat
}