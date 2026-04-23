import { rotate_point, rotate_point_inverse } from '../../utils/rotation';
import { visibleTiles } from '../../vector_tile/visibleTiles';
import { update_path_layer_data } from '../layers/path_layer';
import { update_trx_layer_data } from '../layers/trx_layer';

export const calc_viewport = async (
  { height, width, zoom, target },
  deck_ist,
  layers_obj,
  viz_state
) => {
  const wasCloseUp = viz_state.close_up;
  const { tile_size } = viz_state.img.landscape_parameters;
  const zoomFactor = Math.pow(2, zoom);
  const [targetX, targetY] = target;
  const halfWidthZoomed = width / (2 * zoomFactor);
  const halfHeightZoomed = height / (2 * zoomFactor);

  viz_state.bounds = {};
  viz_state.bounds.min_x = targetX - halfWidthZoomed;
  viz_state.bounds.max_x = targetX + halfWidthZoomed;
  viz_state.bounds.min_y = targetY - halfHeightZoomed;
  viz_state.bounds.max_y = targetY + halfHeightZoomed;

  // Get the current viewport from Deck.gl
  const viewports = deck_ist.viewManager.getViewports();
  if (!viewports || viewports.length === 0) {
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

  if (tiles_in_view.length < viz_state.max_tiles_to_view) {
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      trx_data: false,
      path_data: false,
    });

    viz_state.close_up = true;
    // Update observable - this triggers the image visibility subscriber
    viz_state.obs_store.close_up.set(true);

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

    // gene bar graph update
    const trxCompact = viz_state.combo_data.trx_compact || {
      names: [],
      x: new Float32Array(),
      y: new Float32Array(),
    };
    const geneCounts = new Map();
    for (let i = 0; i < trxCompact.names.length; i++) {
      const x = trxCompact.x[i];
      const y = trxCompact.y[i];
      let inView;
      if (!viz_state.rotation?.hasRotation) {
        inView =
          x >= viz_state.bounds.min_x &&
          x <= viz_state.bounds.max_x &&
          y >= viz_state.bounds.min_y &&
          y <= viz_state.bounds.max_y;
      } else {
        const [rotX, rotY] = rotate_point(x, y, viz_state.rotation);
        inView =
          rotX >= viz_state.bounds.min_x &&
          rotX <= viz_state.bounds.max_x &&
          rotY >= viz_state.bounds.min_y &&
          rotY <= viz_state.bounds.max_y;
      }
      if (!inView) {
        continue;
      }

      const name = trxCompact.names[i];
      geneCounts.set(name, (geneCounts.get(name) || 0) + 1);
    }

    const new_bar_data = Array.from(geneCounts, ([name, value]) => ({
      name,
      value,
    }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 100);

    viz_state.obs_store.new_gene_bar_data.set(new_bar_data);

    // cell bar graph update
    const filtered_cells = viz_state.combo_data.cell.filter((pos) => {
      if (!viz_state.rotation?.hasRotation) {
        return (
          pos.x >= viz_state.bounds.min_x &&
          pos.x <= viz_state.bounds.max_x &&
          pos.y >= viz_state.bounds.min_y &&
          pos.y <= viz_state.bounds.max_y
        );
      }

      const [rotX, rotY] = rotate_point(pos.x, pos.y, viz_state.rotation);

      return (
        rotX >= viz_state.bounds.min_x &&
        rotX <= viz_state.bounds.max_x &&
        rotY >= viz_state.bounds.min_y &&
        rotY <= viz_state.bounds.max_y
      );
    });

    const cellCounts = new Map();
    for (const cell of filtered_cells) {
      cellCounts.set(cell.cat, (cellCounts.get(cell.cat) || 0) + 1);
    }

    const new_bar_data_cell = Array.from(cellCounts, ([name, value]) => ({
      name,
      value,
    })).sort((a, b) => b.value - a.value);

    viz_state.obs_store.new_cell_bar_data.set(new_bar_data_cell);
  } else {
    if (wasCloseUp) {
      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        trx_data: false,
        path_data: false,
      });

      viz_state.close_up = false;
      // Update observable - this triggers the image visibility subscriber
      viz_state.obs_store.close_up.set(false);

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        trx_data: true,
        path_data: true,
      });

      viz_state.obs_store.new_gene_bar_data.set(
        viz_state.genes.top_gene_counts
      );

      viz_state.obs_store.new_cell_bar_data.set(viz_state.cats.cluster_counts);

      viz_state.containers.bar_gene.scrollTo({
        top: 0,
        behavior: 'smooth',
      });

      viz_state.containers.bar_cluster.scrollTo({
        top: 0,
        behavior: 'smooth',
      });
    }
  }

  viz_state.layers_obj = layers_obj;
};
