import { get_image_dimensions } from "../image_tile/get_image_dimensions"
import { options } from "./fetch_options"

export let dimensions = {}

export const set_dimensions = async ( base_url, imgage_name_for_dim ) => {
    
    dimensions = await get_image_dimensions(base_url, imgage_name_for_dim, options)

}