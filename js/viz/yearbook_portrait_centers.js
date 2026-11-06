/**
 * Resolve the spatial center for each cell in a Yearbook page.
 *
 * Per-cell centroids live in the flat scatter-data buffer
 * (`cell_scatter_data.attributes.getPosition.value`) as a typed array with
 * stride = coords-per-cell, indexed via `cell_name_to_index_map`. This replaced
 * an older `cell_scatter_data_objects` array-of-objects buffer that no longer
 * gets populated; reading that dead buffer made every lookup miss and every
 * portrait fall back to the same landscape-center coordinate.
 *
 * @param {string[]} page_cells - cell ids on the current page
 * @param {Map<string, number>} cell_name_to_index_map - cell id -> row index
 * @param {{attributes?: {getPosition?: {value?: ArrayLike<number>, size?: number}}}} cell_scatter_data
 * @param {{x: number, y: number}} fallback_center - used when a cell has no position
 * @returns {{cell_id: string, x: number, y: number}[]}
 */
export const compute_portrait_centers = (
  page_cells,
  cell_name_to_index_map,
  cell_scatter_data,
  fallback_center
) => {
  const position_attr = cell_scatter_data?.attributes?.getPosition;
  const flat_positions = position_attr?.value;
  const stride = position_attr?.size || 2;

  return page_cells.map((cell_id) => {
    const cell_index = cell_name_to_index_map?.get(cell_id);
    if (
      cell_index !== undefined &&
      flat_positions &&
      cell_index * stride + 1 < flat_positions.length
    ) {
      const offset = cell_index * stride;
      return {
        cell_id,
        x: flat_positions[offset],
        y: flat_positions[offset + 1],
      };
    }
    // Fallback to center of image if cell not found
    return {
      cell_id,
      x: fallback_center.x,
      y: fallback_center.y,
    };
  });
};
