import { get_image_dimensions } from '../image_tile/get_image_dimensions';

import { options } from './fetch_options';

export const set_dimensions = async (
  viz_state,
  base_url,
  image_name_for_dim
) => {
  // When using row groups, get dimensions from landscape_parameters
  // since the .dzi files may have been deleted
  if (viz_state.use_row_groups && viz_state.img?.landscape_parameters) {
    const params = viz_state.img.landscape_parameters;

    // Use image_dimensions if available (from DZI parsing during preprocessing)
    if (params.image_dimensions) {
      viz_state.dimensions = {
        width: params.image_dimensions.width,
        height: params.image_dimensions.height,
        tileSize: params.image_dimensions.tile_size || 512,
      };
      console.log(
        `[image_dimensions] Using stored dimensions: ${viz_state.dimensions.width}x${viz_state.dimensions.height}, tileSize=${viz_state.dimensions.tileSize}`
      );
      return;
    }
  }

  // Traditional mode: fetch from .dzi file
  viz_state.dimensions = await get_image_dimensions(
    base_url,
    image_name_for_dim,
    options,
    viz_state.aws
  );
};
