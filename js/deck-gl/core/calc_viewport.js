import { is_point_cloud_technology } from '../../global_variables/image_info';
import {
  areBarDataEqual,
  createEmptyCellCompact,
  createEmptyTrxCompact,
  makeVisibleTileKey,
} from '../../utils/compact_data';
import { rotate_point, rotate_point_inverse } from '../../utils/rotation';
import { visibleTiles } from '../../vector_tile/visibleTiles';
import { update_path_layer_data } from '../layers/path_layer';
import { update_trx_layer_data } from '../layers/trx_layer';

const VIEWPORT_GENE_BAR_LIMIT = 100;

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

const getPointCloudGeneBars = (viz_state) =>
  Array.isArray(viz_state.genes.top_gene_counts)
    ? viz_state.genes.top_gene_counts
    : [];

const computeViewportGeneBars = (viz_state, viewportCache) => {
  const trxCompact =
    viz_state.combo_data.trx_compact || createEmptyTrxCompact();
  const geneCounts = viewportCache.geneCountScratch;
  const activeGeneIds = viewportCache.activeGeneIds;
  activeGeneIds.length = 0;

  const stride = trxCompact.size || 2;

  if (!viz_state.rotation?.hasRotation) {
    for (let i = 0; i < trxCompact.geneIds.length; i++) {
      const positions = trxCompact.positions;
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
  const activeCellIds = viewportCache.activeCellIds;
  activeCellIds.length = 0;

  const stride = cellCompact.size || 2;

  if (!viz_state.rotation?.hasRotation) {
    for (let i = 0; i < cellCompact.categoryIds.length; i++) {
      const positions = cellCompact.positions;
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

export const calc_viewport = async (
  { height, width, zoom, target },
  deck_ist,
  layers_obj,
  viz_state
) => {
  const wasCloseUp = viz_state.close_up;
  const { tile_size } = viz_state.img.landscape_parameters;
  const isPointCloud = is_point_cloud_technology(
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

    return;
  }

  const tile_bounds = (() => {
    if (!viz_state.rotation?.hasRotation) {
      return viz_state.bounds;
    }

    const corners = [
      [viz_state.bounds.min_x, viz_state.bounds.min_y],
      [viz_state.bounds.min_x, viz_state.bounds.max_y],
      [viz_state.bounds.max_x, viz_state.bounds.min_y],
      [viz_state.bounds.max_x, viz_state.bounds.max_y],
    ].map(([x, y]) => rotate_point_inverse(x, y, viz_state.rotation));

    const xs = corners.map(([x]) => x);
    const ys = corners.map(([, y]) => y);

    return {
      min_x: Math.min(...xs),
      max_x: Math.max(...xs),
      min_y: Math.min(...ys),
      max_y: Math.max(...ys),
    };
  })();

  const tiles_in_view = visibleTiles(
    tile_bounds.min_x,
    tile_bounds.max_x,
    tile_bounds.min_y,
    tile_bounds.max_y,
    tile_size
  );
  const visibleTileKey = makeVisibleTileKey(tiles_in_view);

  if (tiles_in_view.length < viz_state.max_tiles_to_view) {
    viz_state.close_up = true;
    viz_state.obs_store.close_up.set(true);

    if (viewportCache.visibleTileKey !== visibleTileKey) {
      if (!isPointCloud) {
        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          trx_data: false,
          path_data: false,
        });

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
