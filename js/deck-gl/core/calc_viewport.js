import { is_orbit_technology } from '../../global_variables/image_info';
import { sync_trx_slider_range } from '../../ui/sliders';
import {
  is_trx_force_shown,
  sync_trx_button,
  trx_force_tile_factor,
  trx_load_tile_limit,
  trx_zone,
  with_trx_loading,
} from '../../ui/trx_handle';
import {
  areBarDataEqual,
  createEmptyCellCompact,
  createEmptyTrxCompact,
  makeVisibleTileKey,
} from '../../utils/compact_data';
import { refresh_layer } from '../../utils/refresh_layer';
import { rotate_point, rotate_point_inverse } from '../../utils/rotation';
import { visibleTiles } from '../../vector_tile/visibleTiles';
import { is_cluster_color_mode } from '../layers/cell_color';
import { refresh_cell_layer_data } from '../layers/cell_layer';
import { build_nbhd_cloud_gene_bar_data } from '../layers/nbhd_cloud_shapes_layer';
import { update_path_layer_data } from '../layers/path_layer';
import { update_trx_layer_data } from '../layers/trx_layer';

const VIEWPORT_GENE_BAR_LIMIT = 200;

/**
 * Entering or leaving intermediate zoom with forced transcripts: cells switch
 * between cluster colors and summed expression (see getVizCellColorContext),
 * and the TRX size slider widens or narrows. Runs before close_up updates, so
 * the slider is back in close-up range before it switches to opacity.
 */
const sync_trx_force_view = (layers_obj, viz_state) => {
  const shown = is_trx_force_shown(viz_state);
  if (shown === Boolean(viz_state.trx_force_shown)) return;
  viz_state.trx_force_shown = shown;

  sync_trx_slider_range(layers_obj, viz_state);
  if (!is_cluster_color_mode(viz_state.cats)) {
    refresh_cell_layer_data(layers_obj, viz_state, {
      updateTriggers: { getFillColor: [viz_state.selection_token, shown] },
    });
    refresh_layer(viz_state, layers_obj, 'cell_layer');
  }
};

const ensureViewportCache = (viz_state) => {
  if (!viz_state.viewport_cache) {
    viz_state.viewport_cache = {
      visibleTileKey: null,
      lastGeneBarData: null,
      lastCellBarData: null,
      geneCountScratch: null,
      activeGeneIds: [],
      cellCountScratch: null,
      activeCellIds: [],
    };
  }

  const geneCountLength = viz_state.genes.gene_names?.length || 0;
  if (
    !viz_state.viewport_cache.geneCountScratch ||
    viz_state.viewport_cache.geneCountScratch.length !== geneCountLength
  ) {
    viz_state.viewport_cache.geneCountScratch = new Uint32Array(
      geneCountLength
    );
    viz_state.viewport_cache.activeGeneIds = [];
  }

  const categoryCountLength =
    viz_state.combo_data.cell_compact?.categoryNames?.length || 0;
  if (
    !viz_state.viewport_cache.cellCountScratch ||
    viz_state.viewport_cache.cellCountScratch.length !== categoryCountLength
  ) {
    viz_state.viewport_cache.cellCountScratch = new Uint32Array(
      categoryCountLength
    );
    viz_state.viewport_cache.activeCellIds = [];
  }

  return viz_state.viewport_cache;
};

const publishBarDataIfChanged = (
  viewportCache,
  cacheKey,
  observable,
  nextData
) => {
  if (
    areBarDataEqual(viewportCache[cacheKey], nextData) &&
    areBarDataEqual(observable.get?.(), nextData)
  ) {
    return;
  }

  viewportCache[cacheKey] = nextData;
  observable.set(nextData);
};

const getPointCloudGeneBars = (viz_state) => {
  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    return build_nbhd_cloud_gene_bar_data(viz_state.nbhd_cloud);
  }
  return Array.isArray(viz_state.genes.top_gene_counts)
    ? viz_state.genes.top_gene_counts
    : [];
};

const computeViewportGeneBars = (viz_state, viewportCache) => {
  const trxCompact =
    viz_state.combo_data.trx_compact || createEmptyTrxCompact();
  const geneCounts = viewportCache.geneCountScratch;
  const { activeGeneIds } = viewportCache;
  activeGeneIds.length = 0;

  const stride = trxCompact.size || 2;

  if (!viz_state.rotation?.hasRotation) {
    for (let i = 0; i < trxCompact.geneIds.length; i++) {
      const { positions } = trxCompact;
      const x = positions[i * stride];
      const y = positions[i * stride + 1];
      if (
        x < viz_state.bounds.min_x ||
        x > viz_state.bounds.max_x ||
        y < viz_state.bounds.min_y ||
        y > viz_state.bounds.max_y
      ) {
        continue;
      }

      const geneId = trxCompact.geneIds[i];
      if (geneId < 0) {
        continue;
      }

      if (geneCounts[geneId] === 0) {
        activeGeneIds.push(geneId);
      }
      geneCounts[geneId] += 1;
    }
  } else {
    for (let i = 0; i < trxCompact.geneIds.length; i++) {
      const x = trxCompact.positions[i * stride];
      const y = trxCompact.positions[i * stride + 1];
      const [rotX, rotY] = rotate_point(x, y, viz_state.rotation);
      if (
        rotX < viz_state.bounds.min_x ||
        rotX > viz_state.bounds.max_x ||
        rotY < viz_state.bounds.min_y ||
        rotY > viz_state.bounds.max_y
      ) {
        continue;
      }

      const geneId = trxCompact.geneIds[i];
      if (geneId < 0) {
        continue;
      }

      if (geneCounts[geneId] === 0) {
        activeGeneIds.push(geneId);
      }
      geneCounts[geneId] += 1;
    }
  }

  activeGeneIds.sort((a, b) => geneCounts[b] - geneCounts[a]);

  const nextGeneBars = activeGeneIds
    .slice(0, VIEWPORT_GENE_BAR_LIMIT)
    .map((geneId) => ({
      name: viz_state.genes.g_nameMapping_inv?.[geneId] ?? String(geneId),
      value: geneCounts[geneId],
    }));

  for (const geneId of activeGeneIds) {
    geneCounts[geneId] = 0;
  }

  return nextGeneBars;
};

const computeViewportCellBars = (viz_state, viewportCache) => {
  const cellCompact =
    viz_state.combo_data.cell_compact || createEmptyCellCompact();
  const cellCounts = viewportCache.cellCountScratch;
  const { activeCellIds } = viewportCache;
  activeCellIds.length = 0;

  const stride = cellCompact.size || 2;

  if (!viz_state.rotation?.hasRotation) {
    for (let i = 0; i < cellCompact.categoryIds.length; i++) {
      const { positions } = cellCompact;
      const x = positions[i * stride];
      const y = positions[i * stride + 1];
      if (
        x < viz_state.bounds.min_x ||
        x > viz_state.bounds.max_x ||
        y < viz_state.bounds.min_y ||
        y > viz_state.bounds.max_y
      ) {
        continue;
      }

      const categoryId = cellCompact.categoryIds[i];
      if (cellCounts[categoryId] === 0) {
        activeCellIds.push(categoryId);
      }
      cellCounts[categoryId] += 1;
    }
  } else {
    for (let i = 0; i < cellCompact.categoryIds.length; i++) {
      const x = cellCompact.positions[i * stride];
      const y = cellCompact.positions[i * stride + 1];
      const [rotX, rotY] = rotate_point(x, y, viz_state.rotation);
      if (
        rotX < viz_state.bounds.min_x ||
        rotX > viz_state.bounds.max_x ||
        rotY < viz_state.bounds.min_y ||
        rotY > viz_state.bounds.max_y
      ) {
        continue;
      }

      const categoryId = cellCompact.categoryIds[i];
      if (cellCounts[categoryId] === 0) {
        activeCellIds.push(categoryId);
      }
      cellCounts[categoryId] += 1;
    }
  }

  activeCellIds.sort((a, b) => cellCounts[b] - cellCounts[a]);

  const nextCellBars = activeCellIds.map((categoryId) => ({
    name: cellCompact.categoryNames[categoryId],
    value: cellCounts[categoryId],
  }));

  for (const categoryId of activeCellIds) {
    cellCounts[categoryId] = 0;
  }

  return nextCellBars;
};

/** Tiles overlapping `bounds` (a view's extent, before rotation). */
const tiles_in_bounds = (bounds, viz_state) => {
  let tile_bounds = bounds;
  if (viz_state.rotation?.hasRotation) {
    const corners = [
      [bounds.min_x, bounds.min_y],
      [bounds.min_x, bounds.max_y],
      [bounds.max_x, bounds.min_y],
      [bounds.max_x, bounds.max_y],
    ].map(([x, y]) => rotate_point_inverse(x, y, viz_state.rotation));
    const xs = corners.map(([x]) => x);
    const ys = corners.map(([, y]) => y);
    tile_bounds = {
      min_x: Math.min(...xs),
      max_x: Math.max(...xs),
      min_y: Math.min(...ys),
      max_y: Math.max(...ys),
    };
  }

  return visibleTiles(
    tile_bounds.min_x,
    tile_bounds.max_x,
    tile_bounds.min_y,
    tile_bounds.max_y,
    viz_state.img.landscape_parameters.tile_size
  );
};

/**
 * Set the TRX button's zoom zone for a view without loading anything. The
 * zone is otherwise only set when the view changes, so a new Landscape uses
 * this for its initial view.
 */
export const set_trx_zone_for_view = (
  { height, width, zoom, target },
  layers_obj,
  viz_state
) => {
  const scale = Math.pow(2, zoom);
  const [x, y] = target;
  const bounds = {
    min_x: x - width / (2 * scale),
    max_x: x + width / (2 * scale),
    min_y: y - height / (2 * scale),
    max_y: y + height / (2 * scale),
  };
  viz_state.trx_zone = trx_zone(
    tiles_in_bounds(bounds, viz_state).length,
    viz_state.max_tiles_to_view,
    trx_force_tile_factor(viz_state)
  );
  sync_trx_button(viz_state, layers_obj);
};

export const calc_viewport = async (
  { height, width, zoom, target },
  deck_ist,
  layers_obj,
  viz_state
) => {
  const wasCloseUp = viz_state.close_up;
  // Kept so a TRX click can re-run this for the current view.
  viz_state.last_viewport_params = { height, width, zoom, target };
  const isPointCloud = is_orbit_technology(
    viz_state.img?.landscape_parameters?.technology
  );

  const zoomFactor = Math.pow(2, zoom);
  const [targetX, targetY] = target;
  const halfWidthZoomed = width / (2 * zoomFactor);
  const halfHeightZoomed = height / (2 * zoomFactor);

  viz_state.bounds = {};
  viz_state.bounds.min_x = targetX - halfWidthZoomed;
  viz_state.bounds.max_x = targetX + halfWidthZoomed;
  viz_state.bounds.min_y = targetY - halfHeightZoomed;
  viz_state.bounds.max_y = targetY + halfHeightZoomed;

  const viewports = deck_ist.viewManager.getViewports();
  if (!viewports || viewports.length === 0) {
    return;
  }

  const viewportCache = ensureViewportCache(viz_state);

  if (isPointCloud) {
    viz_state.close_up = false;
    viz_state.obs_store.close_up.set(false);
    viewportCache.visibleTileKey = null;

    publishBarDataIfChanged(
      viewportCache,
      'lastGeneBarData',
      viz_state.obs_store.new_gene_bar_data,
      getPointCloudGeneBars(viz_state)
    );

    publishBarDataIfChanged(
      viewportCache,
      'lastCellBarData',
      viz_state.obs_store.new_cell_bar_data,
      viz_state.cats.cluster_counts
    );

    // The camera-side reorder check used to live here, but this whole
    // function is behind on_view_state_change's 200ms debounce (see
    // deck_ist.js's set_deck_on_view_state_change) -- fine for the
    // tile/gene-bar work above, which really does want to wait for a quiet
    // period, but it meant the reorder only ever ran up to 200ms after the
    // user *stopped* rotating, not live during the drag.
    // The check itself is O(1) on almost every call (just a sign compare)
    // and only does real work at the rare moment the camera actually
    // crosses the horizon, so it doesn't need debouncing -- it's now called
    // directly from the raw, undebounced onViewStateChange in deck_ist.js
    // instead (check_nbhd_cloud_camera_side).

    return;
  }

  const tiles_in_view = tiles_in_bounds(viz_state.bounds, viz_state);
  const visibleTileKey = makeVisibleTileKey(tiles_in_view);

  // Past the automatic limit, a TRX click (trx_forced) raises it, so
  // intermediate zoom loads transcripts and boundaries as in close-up.
  viz_state.trx_zone = trx_zone(
    tiles_in_view.length,
    viz_state.max_tiles_to_view,
    trx_force_tile_factor(viz_state)
  );
  if (viz_state.trx_zone === 'far') viz_state.trx_forced = false;
  sync_trx_button(viz_state, layers_obj);
  sync_trx_force_view(layers_obj, viz_state);

  if (tiles_in_view.length < trx_load_tile_limit(viz_state)) {
    viz_state.close_up = true;
    viz_state.obs_store.close_up.set(true);

    if (viewportCache.visibleTileKey !== visibleTileKey) {
      if (!isPointCloud) {
        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          trx_data: false,
          path_data: false,
        });

        await with_trx_loading(viz_state, layers_obj, async () => {
          await update_trx_layer_data(
            viz_state.global_base_url,
            tiles_in_view,
            layers_obj,
            viz_state
          );

          await update_path_layer_data(
            viz_state.global_base_url,
            tiles_in_view,
            layers_obj,
            viz_state
          );
        });
      }

      viewportCache.visibleTileKey = visibleTileKey;
    }

    publishBarDataIfChanged(
      viewportCache,
      'lastGeneBarData',
      viz_state.obs_store.new_gene_bar_data,
      isPointCloud
        ? getPointCloudGeneBars(viz_state)
        : computeViewportGeneBars(viz_state, viewportCache)
    );

    publishBarDataIfChanged(
      viewportCache,
      'lastCellBarData',
      viz_state.obs_store.new_cell_bar_data,
      computeViewportCellBars(viz_state, viewportCache)
    );
  } else if (wasCloseUp) {
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      trx_data: false,
      path_data: false,
    });

    viz_state.close_up = false;
    viz_state.obs_store.close_up.set(false);
    viewportCache.visibleTileKey = null;

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      trx_data: true,
      path_data: true,
    });

    publishBarDataIfChanged(
      viewportCache,
      'lastGeneBarData',
      viz_state.obs_store.new_gene_bar_data,
      viz_state.genes.top_gene_counts
    );

    publishBarDataIfChanged(
      viewportCache,
      'lastCellBarData',
      viz_state.obs_store.new_cell_bar_data,
      viz_state.cats.cluster_counts
    );

    viz_state.containers.bar_gene.scrollTo({
      top: 0,
      behavior: 'smooth',
    });

    viz_state.containers.bar_cluster.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  }

  viz_state.layers_obj = layers_obj;
};
