import { fetch_all_tables } from '../../read_parquet/fetch_all_tables.js';
import { get_scatter_data } from '../../read_parquet/get_scatter_data.js';
import { concatenate_arrow_tables } from '../../vector_tile/concatenate_functions.js';
import { set_trx_names_array } from '../../global_variables/trx_names_array.js';
import { options } from '../../global_variables/fetch_options.js';

export let trx_combo_data

export const grab_trx_tiles_in_view = async (base_url, tiles_in_view) => {

    const tile_trx_urls = tiles_in_view.map(tile => {
        return `${base_url}/transcript_tiles/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
    });

    var tile_trx_tables = await fetch_all_tables('trx', tile_trx_urls, options)

    var trx_arrow_table = concatenate_arrow_tables(tile_trx_tables)

    // console.log('trx_arrow_table')
    // console.log(trx_arrow_table)

    var new_trx_names_array = trx_arrow_table.getChild("name").toArray();
    set_trx_names_array(new_trx_names_array)
    var trx_scatter_data = get_scatter_data(trx_arrow_table)

    // Combine names and positions into a single array of objects
    const flatCoordinateArray = trx_scatter_data.attributes.getPosition.value;
    trx_combo_data = new_trx_names_array.map((name, index) => ({
        name,
        x: flatCoordinateArray[index * 2],
        y: flatCoordinateArray[index * 2 + 1]
    }));

    console.log('combined_data', trx_combo_data)

    return trx_scatter_data
}