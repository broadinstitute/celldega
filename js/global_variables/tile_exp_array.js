import { get_new_tile_exp_array } from "../global_variables/tile_scatter_data.js";

export let tile_exp_array 

export const update_tile_exp_array = async (base_url, inst_gene) => {

    const new_tile_exp_array = await get_new_tile_exp_array(base_url, inst_gene)

    tile_exp_array = new_tile_exp_array
}