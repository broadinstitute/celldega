import { visibleTiles } from '../../vector_tile/visibleTiles';
import { update_path_layer_data } from '../layers/path_layer';
import { update_trx_layer_data } from '../layers/trx_layer';

const calc_bounds = ({ height, width, zoom, target }) => {
  const zoomFactor = Math.pow(2, zoom);
  const [targetX, targetY] = target;
  const halfWidthZoomed = width / (2 * zoomFactor);
  const halfHeightZoomed = height / (2 * zoomFactor);

  return {
    min_x: targetX - halfWidthZoomed,
    max_x: targetX + halfWidthZoomed,
    min_y: targetY - halfHeightZoomed,
    max_y: targetY + halfHeightZoomed,
  };
};

const normalize_view_states = (view_state, deck_ist, viz_state) => {
  if (viz_state.yearbook?.active) {
    const viewports = deck_ist.viewManager?.getViewports?.();
    if (!viewports || viewports.length === 0) {
      return [];
    }

    return viewports.map((viewport) => {
      const { zoom, target } = viewport.viewState || viewport;
      return {
        width: viewport.width,
        height: viewport.height,
        zoom,
        target,
      };
    });
  }

  return [view_state];
};

export const calc_viewport = async (
  view_state,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const view_states = normalize_view_states(view_state, deck_ist, viz_state);
  if (view_states.length === 0) {
    return;
  }

  const wasCloseUp = viz_state.close_up;
  const { tile_size } = viz_state.img.landscape_parameters;

  const bounds_list = view_states.map((state) => calc_bounds(state));
  viz_state.bounds_list = bounds_list;

  const tiles_map = new Map();
  bounds_list.forEach((bounds) => {
    visibleTiles(
      bounds.min_x,
      bounds.max_x,
      bounds.min_y,
      bounds.max_y,
      tile_size
    ).forEach((tile) => tiles_map.set(tile.name, tile));
  });

  const tiles_in_view = Array.from(tiles_map.values());

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
    const filtered_transcripts = viz_state.combo_data.trx.filter(
      (pos) =>
        bounds_list.some(
          (bounds) =>
            pos.x >= bounds.min_x &&
            pos.x <= bounds.max_x &&
            pos.y >= bounds.min_y &&
            pos.y <= bounds.max_y
        )
    );

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
    const filtered_cells = viz_state.combo_data.cell.filter(
      (pos) =>
        bounds_list.some(
          (bounds) =>
            pos.x >= bounds.min_x &&
            pos.x <= bounds.max_x &&
            pos.y >= bounds.min_y &&
            pos.y <= bounds.max_y
        )
    );

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
