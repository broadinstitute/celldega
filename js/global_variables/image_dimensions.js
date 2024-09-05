import { get_image_dimensions } from "../image_tile/get_image_dimensions"
import { options } from "./fetch_options"

export const set_dimensions = async (viz_state, base_url, imgage_name_for_dim ) => {

    viz_state.dimensions = await get_image_dimensions(base_url, imgage_name_for_dim, options)

}