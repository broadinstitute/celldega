import { OrthographicView } from 'deck.gl';

import { visibleTiles } from '../../vector_tile/visibleTiles';

/**
 * Create multiple OrthographicViews for the yearbook grid layout.
 * Each portrait gets its own view with specific x, y, width, height.
 *
 * @param {number} num_rows - Number of rows in the grid
 * @param {number} num_cols - Number of columns in the grid
 * @param {number} portrait_size - Size of each portrait in pixels
 * @param {number} gap - Gap between portraits in pixels
 * @returns {Array<OrthographicView>} Array of deck.gl views
 */
export const create_yearbook_views = (
  num_rows,
  num_cols,
  portrait_size,
  gap
) => {
  const views = [];

  for (let row = 0; row < num_rows; row++) {
    for (let col = 0; col < num_cols; col++) {
      const index = row * num_cols + col;

      // Calculate the position of this portrait
      const x = col * (portrait_size + gap);
      const y = row * (portrait_size + gap);

      views.push(
        new OrthographicView({
          id: `portrait-${index}`,
          x,
          y,
          width: portrait_size,
          height: portrait_size,
          controller: {
            doubleClickZoom: false,
            dragPan: false, // Disable panning in yearbook
            scrollZoom: true, // Enable zoom
            touchZoom: true,
          },
        })
      );
    }
  }

  return views;
};

/**
 * Calculate the viewport bounds for each portrait based on its center.
 * When zoom=0, view_width and view_height should be in data/image coordinates.
 *
 * @param {Array<{cell_id: string, x: number, y: number}>} centers - Center coordinates for each portrait
 * @param {number} zoom - Current zoom level (use 0 if view dimensions are already in data coords)
 * @param {number} view_width - Width of each portrait view (in data coordinates when zoom=0)
 * @param {number} view_height - Height of each portrait view (in data coordinates when zoom=0)
 * @returns {Array<{min_x, max_x, min_y, max_y}>} Viewport bounds for each portrait
 */
export const calc_portrait_viewports = (
  centers,
  zoom,
  view_width,
  view_height
) => {
  const zoomFactor = Math.pow(2, zoom);
  const halfWidthZoomed = view_width / (2 * zoomFactor);
  const halfHeightZoomed = view_height / (2 * zoomFactor);

  return centers.map((center) => ({
    cell_id: center.cell_id,
    min_x: center.x - halfWidthZoomed,
    max_x: center.x + halfWidthZoomed,
    min_y: center.y - halfHeightZoomed,
    max_y: center.y + halfHeightZoomed,
    center_x: center.x,
    center_y: center.y,
  }));
};

/**
 * Get tiles visible across all portraits (discontiguous tile loading).
 * This returns a unique set of tiles that cover all portrait viewports.
 *
 * @param {Array<{cell_id: string, x: number, y: number}>} centers - Center coordinates for each portrait
 * @param {number} zoom - Current zoom level
 * @param {number} view_width - Width of each portrait view in pixels
 * @param {number} view_height - Height of each portrait view in pixels
 * @param {number} tile_size - Size of each tile
 * @returns {Array<{tileX: number, tileY: number, name: string}>} Unique tiles across all viewports
 */
export const get_discontiguous_tiles = (
  centers,
  zoom,
  view_width,
  view_height,
  tile_size
) => {
  const viewports = calc_portrait_viewports(
    centers,
    zoom,
    view_width,
    view_height
  );

  // Collect all tiles from all viewports
  const tile_map = new Map();

  viewports.forEach((viewport) => {
    const tiles = visibleTiles(
      viewport.min_x,
      viewport.max_x,
      viewport.min_y,
      viewport.max_y,
      tile_size
    );

    tiles.forEach((tile) => {
      // Use tile name as key to deduplicate
      if (!tile_map.has(tile.name)) {
        tile_map.set(tile.name, tile);
      }
    });
  });

  return Array.from(tile_map.values());
};

/**
 * Create initial view states for all portraits.
 *
 * @param {Array<{cell_id: string, x: number, y: number}>} centers - Center coordinates for each portrait
 * @param {number} zoom - Initial zoom level
 * @returns {Object} View states keyed by view id
 */
export const create_initial_view_states = (centers, zoom) => {
  const view_states = {};

  centers.forEach((center, index) => {
    const view_id = `portrait-${index}`;
    view_states[view_id] = {
      target: [center.x, center.y, 0],
      zoom,
    };
  });

  return view_states;
};

/**
 * Update all view states with a new zoom level (keeping centers the same).
 *
 * @param {Object} current_view_states - Current view states
 * @param {number} new_zoom - New zoom level
 * @returns {Object} Updated view states
 */
export const update_view_states_zoom = (current_view_states, new_zoom) => {
  const updated_states = {};

  Object.entries(current_view_states).forEach(([view_id, state]) => {
    updated_states[view_id] = {
      ...state,
      zoom: new_zoom,
    };
  });

  return updated_states;
};

/**
 * Calculate the total portraits per page.
 *
 * @param {number} num_rows - Number of rows
 * @param {number} num_cols - Number of columns
 * @returns {number} Total portraits per page
 */
export const get_portraits_per_page = (num_rows, num_cols) => {
  return num_rows * num_cols;
};

/**
 * Calculate total pages needed.
 *
 * @param {number} total_cells - Total number of cells
 * @param {number} num_rows - Number of rows
 * @param {number} num_cols - Number of columns
 * @returns {number} Total pages
 */
export const get_total_pages = (total_cells, num_rows, num_cols) => {
  const portraits_per_page = get_portraits_per_page(num_rows, num_cols);
  return Math.max(1, Math.ceil(total_cells / portraits_per_page));
};

/**
 * Get cells for a specific page.
 *
 * @param {Array<string>} cells - All cell ids
 * @param {number} page - Page number (0-indexed)
 * @param {number} num_rows - Number of rows
 * @param {number} num_cols - Number of columns
 * @returns {Array<string>} Cell ids for the page
 */
export const get_cells_for_page = (cells, page, num_rows, num_cols) => {
  const portraits_per_page = get_portraits_per_page(num_rows, num_cols);
  const start_index = page * portraits_per_page;
  return cells.slice(start_index, start_index + portraits_per_page);
};

/**
 * Filter data points to those visible in any portrait.
 *
 * @param {Array<{x: number, y: number}>} data - Data points with x, y coordinates
 * @param {Array<{min_x, max_x, min_y, max_y}>} viewports - Viewport bounds
 * @returns {Array} Filtered data points
 */
export const filter_data_in_viewports = (data, viewports) => {
  return data.filter((point) => {
    return viewports.some(
      (viewport) =>
        point.x >= viewport.min_x &&
        point.x <= viewport.max_x &&
        point.y >= viewport.min_y &&
        point.y <= viewport.max_y
    );
  });
};
