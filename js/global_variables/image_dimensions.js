import { get_image_dimensions } from '../image_tile/get_image_dimensions';

import { options } from './fetch_options';

export const set_dimensions = async (
  viz_state,
  base_url,
  image_name_for_dim
) => {
  // Always try to get dimensions from .dzi file first
  // We keep .dzi files even in row groups mode since they're tiny and useful
  try {
    viz_state.dimensions = await get_image_dimensions(
      base_url,
      image_name_for_dim,
      options,
      viz_state.aws
    );
    return;
  } catch {
    // console.log(`[image_dimensions] DZI fetch failed: ${error.message}`);
  }

  // Fallback for row groups mode when DZI is unavailable
  if (viz_state.use_row_groups && viz_state.img?.landscape_parameters) {
    const params = viz_state.img.landscape_parameters;

    // Use image_dimensions if available
    if (params.image_dimensions?.width && params.image_dimensions?.height) {
      viz_state.dimensions = {
        width: params.image_dimensions.width,
        height: params.image_dimensions.height,
        tileSize: params.image_dimensions.tile_size || 512,
      };
      // console.log(
      //   `[image_dimensions] From stored params: ${viz_state.dimensions.width}x${viz_state.dimensions.height}`
      // );
      return;
    }

    // Calculate from image reader's zoom info
    if (viz_state.row_group_readers?.images) {
      const firstReader = Object.values(viz_state.row_group_readers.images)[0];
      if (firstReader?.zoomInfo) {
        const zoomLevels = Object.keys(firstReader.zoomInfo)
          .map(Number)
          .sort((a, b) => b - a);
        const maxZoom = zoomLevels[0];
        const maxZoomInfo = firstReader.zoomInfo[String(maxZoom)];

        if (maxZoomInfo) {
          const tileSize = 512;
          const width = maxZoomInfo.num_tiles_x * tileSize;
          const height = maxZoomInfo.num_tiles_y * tileSize;

          viz_state.dimensions = { width, height, tileSize };
          // console.log(
          //   `[image_dimensions] Calculated from zoom ${maxZoom}: ${width}x${height}`
          // );
          return;
        }
      }
    }
  }

  // Last resort fallback
  // console.error('[image_dimensions] Could not determine image dimensions');
  viz_state.dimensions = { width: 10000, height: 10000, tileSize: 512 };
};
