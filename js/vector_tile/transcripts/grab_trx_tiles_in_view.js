// import {}

// export const grab_trx_tiles_in_view = async (tiles_in_view, options) => {

//   const tile_trx_urls = tiles_in_view.map(tile => {
//       return `${base_url}/transcript_tiles/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
//   });

//   var tile_trx_tables = await fetch_all_tables(cache_trx, tile_trx_urls, options)
//   var trx_arrow_table = concatenate_arrow_tables(tile_trx_tables)
//   var new_trx_names_array = trx_arrow_table.getChild("name").toArray();
//   set_trx_names_array(new_trx_names_array)
//   var trx_scatter_data = get_scatter_data(trx_arrow_table)

//   return trx_scatter_data
// }