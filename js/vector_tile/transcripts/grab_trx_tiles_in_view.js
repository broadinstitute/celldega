import { options } from '../../global_variables/fetch_options';
import { fetch_all_tables_new } from '../../read_parquet/fetch_all_tables';
import { get_scatter_data } from '../../read_parquet/get_scatter_data';
import { concatenate_arrow_tables } from '../../vector_tile/concatenate_functions';

export const grab_trx_tiles_in_view = async (
  base_url,
  tiles_in_view,
  viz_state
) => {
  const tile_trx_urls = tiles_in_view.map((tile) => {
    return `${base_url}/transcript_tiles/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
  });

  const tile_trx_tables_ini = await fetch_all_tables_new(
    viz_state.cache.trx,
    tile_trx_urls,
    options,
    viz_state.aws
  );

  const tile_trx_tables = tile_trx_tables_ini.filter((table) => table !== null);

  const trx_arrow_table = concatenate_arrow_tables(tile_trx_tables);

  // Handle case where no transcript tiles were loaded
  if (!trx_arrow_table) {
    viz_state.genes.trx_names_array = [];
    viz_state.combo_data.trx = [];
    return {
      length: 0,
      attributes: {
        getPosition: { value: new Float32Array(), size: 2 },
      },
    };
  }

  let new_trx_names_array = [];
  if (!viz_state.vector_name_integer) {
    // extract names directly.
    new_trx_names_array = trx_arrow_table.getChild('name')?.toArray() || [];
  } else {
    // map integer values to strings.
    const names_child = trx_arrow_table.getChild('name');
    new_trx_names_array = names_child
      ? Array.from(names_child.toArray()).map(
          (num) => viz_state.genes.g_nameMapping_inv[num]
        )
      : [];
  }

  viz_state.genes.trx_names_array = new_trx_names_array;

  const trx_scatter_data = get_scatter_data(trx_arrow_table);

  // Combine names and positions into a single array of objects
  const flatCoordinateArray = trx_scatter_data.attributes.getPosition.value;
  viz_state.combo_data.trx = viz_state.genes.trx_names_array.map(
    (name, index) => ({
      name,
      x: flatCoordinateArray[index * 2],
      y: flatCoordinateArray[index * 2 + 1],
    })
  );

  return trx_scatter_data;
};
