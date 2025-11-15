import { rotatePoint, rotatePointInverse } from '../../utils/rotation';
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

  const tileBounds = (() => {
    if (!viz_state.rotation?.hasRotation) {
      return viz_state.bounds;
    }

    const corners = [
      [viz_state.bounds.min_x, viz_state.bounds.min_y],
      [viz_state.bounds.min_x, viz_state.bounds.max_y],
      [viz_state.bounds.max_x, viz_state.bounds.min_y],
      [viz_state.bounds.max_x, viz_state.bounds.max_y],
    ].map(([x, y]) => rotatePointInverse(x, y, viz_state.rotation));

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
    tileBounds.min_x,
    tileBounds.max_x,
    tileBounds.min_y,
    tileBounds.max_y,
    tile_size
  );

  if (tiles_in_view.length < viz_state.max_tiles_to_view) {
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      trx_data: false,
      path_data: false,
    });

    viz_state.close_up = true;

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
    const filtered_transcripts = viz_state.combo_data.trx.filter((pos) => {
      if (!viz_state.rotation?.hasRotation) {
        return (
          pos.x >= viz_state.bounds.min_x &&
          pos.x <= viz_state.bounds.max_x &&
          pos.y >= viz_state.bounds.min_y &&
          pos.y <= viz_state.bounds.max_y
        );
      }

      const [rotX, rotY] = rotatePoint(pos.x, pos.y, viz_state.rotation);

      return (
        rotX >= viz_state.bounds.min_x &&
        rotX <= viz_state.bounds.max_x &&
        rotY >= viz_state.bounds.min_y &&
        rotY <= viz_state.bounds.max_y
      );
    });

    const filtered_gene_names = filtered_transcripts.map(
      (transcript) => transcript.name
    );

    const new_bar_data = filtered_gene_names
      .reduce((acc, gene) => {
        const existingGene = acc.find((item) => item.name === gene);
        if (existingGene) {
          existingGene.value += 1;
        } else {
          acc.push({ name: gene, value: 1 });
        }
        return acc;
      }, [])
      .filter((item) => item.value > 0)
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

      const [rotX, rotY] = rotatePoint(pos.x, pos.y, viz_state.rotation);

      return (
        rotX >= viz_state.bounds.min_x &&
        rotX <= viz_state.bounds.max_x &&
        rotY >= viz_state.bounds.min_y &&
        rotY <= viz_state.bounds.max_y
      );
    });

    const filtered_cell_names = filtered_cells.map((cell) => cell.cat);

    const new_bar_data_cell = filtered_cell_names
      .reduce((acc, cat) => {
        const existing_cat = acc.find((item) => item.name === cat);
        if (existing_cat) {
          existing_cat.value += 1;
        } else {
          acc.push({ name: cat, value: 1 });
        }
        return acc;
      }, [])
      .filter((item) => item.value > 0)
      .sort((a, b) => b.value - a.value);

    viz_state.obs_store.new_cell_bar_data.set(new_bar_data_cell);
  } else {
    if (wasCloseUp) {
      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        trx_data: false,
        path_data: false,
      });

      viz_state.close_up = false;

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
