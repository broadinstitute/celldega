import { fetch_all_tables_new } from '../../read_parquet/fetch_all_tables.js'
import { get_polygon_data } from '../../read_parquet/get_polygon_data.js'
import { concatenate_polygon_data } from '../concatenate_functions.js'
import { extractPolygonPaths } from './extractPolygonPaths.js'
import { options } from '../../global_variables/fetch_options.js'

export const grab_cell_tiles_in_view = async (base_url, tiles_in_view, viz_state) => {

    let segmentation_url;

    if (viz_state.seg.version === 'default'){
        segmentation_url = base_url + '/cell_segmentation';
    } else {
        segmentation_url = base_url + '/cell_segmentation_' + viz_state.seg.version;
    }

    const tile_cell_urls = tiles_in_view.map(tile => {
        return `${segmentation_url}/cell_tile_${tile.tileX}_${tile.tileY}.parquet`;
    });

    var tile_cell_tables_ini_new = await fetch_all_tables_new(viz_state.cache.cell, tile_cell_urls, options)

    var tile_cell_tables = tile_cell_tables_ini_new.filter(table => table !== null);

    if (!viz_state.vector_name_integer) {
        // When viz_state.vector_name_integer is false, use the direct extraction.
        viz_state.cats.polygon_cell_names = tile_cell_tables.flatMap(table =>
          Array.from(table.getChild('name').toArray())
        );
      } else {
        // When viz_state.vector_name_integer is true, map the integers to their string values.
        viz_state.cats.polygon_cell_names = tile_cell_tables.flatMap(table => {
          const intNames = Array.from(table.getChild('name').toArray());
          return intNames.map(num => viz_state.cats.nameMapping_inv[num]);
        });
      }

    var polygon_datas = tile_cell_tables.map(x => get_polygon_data(x))

    var polygon_data = concatenate_polygon_data(polygon_datas);

    var polygonPathsConcat = extractPolygonPaths(polygon_data)

    return polygonPathsConcat
}