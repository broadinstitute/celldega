import { options } from '../../global_variables/fetch_options';
import { fetch_all_tables_new } from '../../read_parquet/fetch_all_tables';
import { get_polygon_data } from '../../read_parquet/get_polygon_data';
import { concatenate_polygon_data } from '../concatenate_functions';

import { extractPolygonPaths } from './extractPolygonPaths';

/**
 * Fetch cell tiles from row group reader
 * @param {Array} tiles_in_view - Array of tiles with tileX and tileY
 * @param {Object} viz_state - Visualization state containing row_group_readers
 * @returns {Promise<arrow.Table|null>} - Arrow table for requested tiles
 */
async function grab_cell_tiles_row_groups(tiles_in_view, viz_state) {
  const reader = viz_state.row_group_readers?.cell;
  if (!reader) {
    // console.error('[grab_cell_tiles] Row group reader not initialized');
    return null;
  }

  // Convert tile format from {tileX, tileY} to {tile_x, tile_y}
  const tilesForReader = tiles_in_view.map((tile) => ({
    tile_x: tile.tileX,
    tile_y: tile.tileY,
  }));

  return reader.readTiles(tilesForReader);
}

/**
 * Extract cell names from table(s), handling both individual tables and row-grouped tables
 * @param {Array|arrow.Table} tables - Array of tables or single table
 * @param {boolean} integerNames - Whether names need integer-to-string mapping
 * @param {Object} nameMapping - Integer-to-string cell name mapping
 * @returns {Array} - Array of cell names
 */
function extractCellNames(tables, integerNames, nameMapping) {
  // Normalize to array
  const tableArray = Array.isArray(tables) ? tables : [tables];

  if (!integerNames) {
    // When names are strings, use the direct extraction.
    return tableArray.flatMap((table) => {
      const name_child = table.getChild('name');
      return name_child ? Array.from(name_child.toArray()) : [];
    });
  } else {
    // Map integer names to their string values.
    return tableArray.flatMap((table) => {
      const name_child = table.getChild('name');
      if (!name_child) return [];
      const intNames = Array.from(name_child.toArray());
      return intNames.map((num) => nameMapping[num]);
    });
  }
}

/** Fetch matching geometry and IDs without publishing either to live state. */
export const grab_cell_tiles_in_view = async (
  base_url,
  tiles_in_view,
  viz_state
) => {
  // Keep the names paired with the geometry from this request. Publishing them
  // here would let an older fetch overwrite a newer layer's color/picking IDs.
  const integerNames = viz_state.vector_name_integer;
  const nameMapping = viz_state.cats.nameMapping_inv;

  // Check if using row group mode
  if (viz_state.use_row_groups && viz_state.row_group_readers?.cell) {
    const cell_table = await grab_cell_tiles_row_groups(
      tiles_in_view,
      viz_state
    );

    if (!cell_table) {
      return { paths: [], cellNames: [] };
    }

    // Extract cell names from the combined table
    const cellNames = extractCellNames(cell_table, integerNames, nameMapping);

    // Get polygon data directly from the combined table
    const polygon_data = get_polygon_data(cell_table);
    const polygonPathsConcat = extractPolygonPaths(polygon_data);

    return { paths: polygonPathsConcat, cellNames };
  }

  // Traditional mode: fetch individual tile files
  let segmentation_url;

  if (viz_state.seg.version === 'default') {
    segmentation_url = `${base_url}/cell_segmentation`;
  } else {
    segmentation_url = `${base_url}/cell_segmentation_${viz_state.seg.version}`;
  }

  const tile_cell_urls = tiles_in_view.map((tile) => {
    return `${segmentation_url}/cell_tile_${tile.tileX}_${tile.tileY}.parquet`;
  });

  const tile_cell_tables_ini_new = await fetch_all_tables_new(
    viz_state.cache.cell,
    tile_cell_urls,
    options,
    viz_state.aws
  );

  const tile_cell_tables = tile_cell_tables_ini_new.filter(
    (table) => table !== null
  );

  // Handle case where no cell tiles were loaded
  if (tile_cell_tables.length === 0) {
    return { paths: [], cellNames: [] };
  }

  // Extract cell names
  const cellNames = extractCellNames(
    tile_cell_tables,
    integerNames,
    nameMapping
  );

  const polygon_datas = tile_cell_tables.map((x) => get_polygon_data(x));

  const polygon_data = concatenate_polygon_data(polygon_datas);

  const polygonPathsConcat = extractPolygonPaths(polygon_data);

  return { paths: polygonPathsConcat, cellNames };
};
