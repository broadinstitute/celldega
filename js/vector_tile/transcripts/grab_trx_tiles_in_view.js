import { concatenate_arrow_tables } from '../concatenate_functions.js';
import { fetch_all_tables } from '../../read_parquet/fetch_all_tables.js';
import { get_scatter_data } from '../../read_parquet/get_scatter_data.js';

export const grab_trx_tiles_in_view = async (
    tiles_in_view, 
    options,
    base_url,
    cache_trx, 
    trx_names_array
    ) => {

    console.log('grab_trx_ties_in_view')

    const tile_trx_urls = tiles_in_view.map(tile => {
    return `${base_url}/real_transcript_tiles_mosaic/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
    });

    var tile_trx_tables = await fetch_all_tables(cache_trx, tile_trx_urls, options)
    var trx_arrow_table = concatenate_arrow_tables(tile_trx_tables)

    trx_names_array = trx_arrow_table.getChild("name").toArray();

    var trx_scatter_data = get_scatter_data(trx_arrow_table)

    return  {
        trx_scatter_data, 
        trx_names_array
    }

}