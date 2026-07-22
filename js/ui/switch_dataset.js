import { ini_background_layer } from '../deck-gl/layers/background_layer';
import {
  refresh_cell_layer_data,
  set_point_cloud_cell_position_buffers,
  set_point_cloud_umap_positions_from_names,
  set_scatterplot_umap_positions_from_names,
  set_spatial_bounds_from_flat_coordinates,
} from '../deck-gl/layers/cell_layer';
import { make_image_layers } from '../deck-gl/layers/image_layers';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import {
  set_cell_cats,
  set_dict_cell_cats,
  update_cat,
  update_selected_cats,
} from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import {
  set_cell_names_array,
  set_cell_name_to_index_map,
} from '../global_variables/cell_names_array';
import { set_color_dict_gene } from '../global_variables/color_dict_gene';
import { options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_dimensions } from '../global_variables/image_dimensions';
import {
  get_landscape_image_info,
  get_primary_image_name,
  is_point_cloud_technology,
  set_image_info,
  set_image_layer_colors,
  set_image_format,
  technology_has_image_layer,
} from '../global_variables/image_info';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_cluster_metadata } from '../global_variables/meta_cluster';
import { set_meta_gene } from '../global_variables/meta_gene';
import { update_selected_genes } from '../global_variables/selected_genes';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { get_scatter_data } from '../read_parquet/get_scatter_data';
import {
  buildCellCompactData,
  createEmptyCellCompact,
  createEmptyTrxCompact,
} from '../utils/compact_data';

import { set_image_layer_sliders } from './sliders';

/**
 * Save the current visualization state before switching datasets
 * @param {Object} viz_state - The visualization state object
 * @returns {Object} Saved state object
 */
const save_persistent_state = (viz_state) => {
  return {
    selected_cats: [...viz_state.cats.selected_cats],
    selected_genes: [...viz_state.genes.selected_genes],
    cat: viz_state.cats.cat,
    viz_image_layers: viz_state.obs_store.viz_image_layers.get(),
    landscape_view: viz_state.obs_store.landscape_view.get(),
  };
};

/**
 * Restore visualization state after switching datasets
 * Only restores selections that exist in the new dataset
 * @param {Object} viz_state - The visualization state object
 * @param {Object} layers_obj - The layers object
 * @param {Object} saved_state - Previously saved state
 */
const restore_persistent_state = async (viz_state, layers_obj, saved_state) => {
  // Restore landscape view (UMAP vs spatial)
  if (viz_state.umap.has_umap) {
    viz_state.obs_store.landscape_view.set(saved_state.landscape_view);
  }

  // Check if selected genes exist in new dataset and restore
  const valid_genes = saved_state.selected_genes.filter((gene) =>
    viz_state.genes.gene_names.includes(gene)
  );

  if (valid_genes.length > 0) {
    const inst_gene = valid_genes[0];

    // Load gene expression data for the new dataset FIRST
    // This ensures cell_exp_array is populated before we update the layer
    await update_cell_exp_array(
      viz_state.cats,
      viz_state.genes,
      viz_state.global_base_url,
      inst_gene,
      viz_state.seg.version,
      viz_state.vector_name_integer,
      viz_state.aws,
      viz_state.row_group_readers?.cbg
    );

    // Now update cat and selections AFTER expression data is loaded
    update_cat(viz_state.cats, inst_gene);
    update_selected_genes(viz_state.genes, valid_genes, viz_state.obs_store);
    update_selected_cats(viz_state.cats, valid_genes, viz_state.obs_store);

    // Image visibility is automatically updated via obs_store subscription
    // when selected_genes changes (based on current close_up state)

    // Force cell layer to refresh with new expression data
    viz_state.selection_token = (viz_state.selection_token || 0) + 1;
    refresh_cell_layer_data(layers_obj, viz_state, {
      id: `cell-layer-gene-${inst_gene}-${viz_state.selection_token}`,
    });
    viz_state.layers_obj = layers_obj;
  } else {
    // No valid gene selection, check for cluster selection
    // Get available clusters in the new dataset
    const available_clusters = new Set(
      viz_state.cats.cluster_counts.map((c) => c.name)
    );

    // Filter to only clusters that exist in the new dataset
    const valid_cats = saved_state.selected_cats.filter((cat) =>
      available_clusters.has(cat)
    );

    if (valid_cats.length > 0) {
      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, valid_cats, viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      // Image visibility is automatically updated via obs_store subscription
      // when selected_cats changes (based on current close_up state)
    } else {
      // No gene or cluster selected - clear selections to restore normal view
      update_selected_cats(viz_state.cats, [], viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);
      // Image visibility will be restored automatically by the subscriber
    }
  }

  // Update persistent_state observable
  viz_state.obs_store.persistent_state.set({
    selected_cats: viz_state.cats.selected_cats,
    selected_genes: viz_state.genes.selected_genes,
    cat: viz_state.cats.cat,
    viz_image_layers: viz_state.obs_store.viz_image_layers.get(),
    landscape_view: saved_state.landscape_view,
  });
};

/**
 * Switch to a different dataset by updating layers and state without rebuilding deck.gl.
 * This approach avoids accumulating WebGL contexts.
 *
 * @param {number} new_index - The index of the dataset to switch to
 * @param {Object} viz_state - The visualization state object
 * @param {Object} deck_ist - The deck.gl instance
 * @param {Object} layers_obj - The layers object
 */
export const switch_dataset = async (
  new_index,
  viz_state,
  deck_ist,
  layers_obj
) => {
  const base_urls = viz_state.base_urls || [];

  if (new_index < 0 || new_index >= base_urls.length) {
    return;
  }

  // Save current state before switching (for persistence across datasets)
  const saved_state = save_persistent_state(viz_state);

  // Mark that we're switching datasets
  viz_state.obs_store.dataset_switching.set(true);

  // Temporarily disable deck rendering updates
  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    background_layer: false,
    image_layers: false,
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });

  try {
    const new_dataset = base_urls[new_index];
    const new_base_url = new_dataset.url;

    // Update global base URL
    set_global_base_url(viz_state, new_base_url);

    // Load new landscape parameters
    await set_landscape_parameters(viz_state.img, new_base_url, viz_state.aws);

    const { landscape_parameters } = viz_state.img;
    const { technology: tech, image_format } = landscape_parameters;
    const pointCloud = is_point_cloud_technology(tech);
    const has_image_layer = technology_has_image_layer(tech);
    const tmp_image_info = get_landscape_image_info(landscape_parameters);
    const image_name_for_dim = get_primary_image_name(landscape_parameters);

    if (!has_image_layer) {
      viz_state.obs_store.viz_image_layers.set(false);
      viz_state.obs_store.viz_background_layer.set(false);
    }

    // Update image format and info
    set_image_format(viz_state.img, image_format);
    set_image_info(viz_state.img, tmp_image_info);
    set_image_layer_sliders(viz_state.img);
    set_image_layer_colors(
      viz_state.img.image_layer_colors,
      viz_state.img.image_info
    );

    // Update dimensions
    if (has_image_layer) {
      await set_dimensions(viz_state, new_base_url, image_name_for_dim);
    } else {
      viz_state.dimensions = { width: 1, height: 1, tileSize: 1 };
    }

    // Load new meta_gene data
    viz_state.genes.gene_counts = [];
    viz_state.genes.meta_gene = {};
    await set_meta_gene(
      viz_state.genes,
      new_base_url,
      viz_state.seg.version,
      viz_state.aws
    );
    viz_state.genes.top_gene_counts = viz_state.genes.gene_counts.slice(0, 100);

    // Update gene bar data
    viz_state.obs_store.new_gene_bar_data.set(viz_state.genes.top_gene_counts);

    // Load new color dict for genes
    await set_color_dict_gene(
      viz_state.genes,
      new_base_url,
      viz_state.seg.version,
      viz_state.aws
    );

    // Load new cell metadata. An alignment variant overrides only the
    // cell_metadata positions file; clusters/genes still key off seg.version.
    let cell_url;
    const cell_meta_version =
      viz_state.alignment && viz_state.alignment !== 'default'
        ? viz_state.alignment
        : viz_state.seg.version;
    if (!cell_meta_version || cell_meta_version === 'default') {
      cell_url = `${new_base_url}/cell_metadata.parquet`;
    } else {
      cell_url = `${new_base_url}/cell_metadata_${cell_meta_version}.parquet`;
    }

    const cell_arrow_table = await get_arrow_table(
      cell_url,
      options.fetch,
      viz_state.aws
    );
    set_cell_names_array(viz_state.cats, cell_arrow_table);
    viz_state.spatial.cell_scatter_data = get_scatter_data(cell_arrow_table);

    if (pointCloud && viz_state.vector_name_integer) {
      viz_state.cats.cell_name_to_index_map = new Map();
    } else {
      set_cell_name_to_index_map(viz_state.cats);
    }

    // Load cluster data
    if (viz_state.cats.has_meta_cell) {
      const inst_index = viz_state.cats.meta_cell_attr.indexOf(
        viz_state.cats.inst_cell_attr
      );
      viz_state.cats.cell_cats = viz_state.cats.cell_names_array.map((name) => {
        const attrs = viz_state.cats.meta_cell[name];
        return attrs?.[inst_index] ?? 'N.A.';
      });
    } else {
      const cluster_arrow_table = await get_arrow_table(
        `${new_base_url}/cell_clusters${viz_state.seg.version && viz_state.seg.version !== 'default' ? `_${viz_state.seg.version}` : ''}/cluster.parquet`,
        options.fetch,
        viz_state.aws
      );
      set_cell_cats(viz_state.cats, cluster_arrow_table, 'cluster');
    }

    if (pointCloud) {
      viz_state.cats.dict_cell_cats = {};
      viz_state.cats.has_dict_cell_cats = false;
    } else {
      set_dict_cell_cats(viz_state.cats);
    }

    // Reset cluster metadata and counts
    viz_state.cats.color_dict_cluster = {};
    viz_state.cats.cluster_counts = [];
    await set_cluster_metadata(viz_state);

    // Update cell bar data
    viz_state.obs_store.new_cell_bar_data.set(viz_state.cats.cluster_counts);

    // Rebuild cell scatter data objects
    const new_cell_names_array = viz_state.cats.cell_names_array;
    const flatCoordinateArray =
      viz_state.spatial.cell_scatter_data.attributes.getPosition.value;
    const dim =
      viz_state.spatial.cell_scatter_data.attributes.getPosition.size || 2;
    const numRows = viz_state.spatial.cell_scatter_data.length;
    viz_state.combo_data.cell_compact = pointCloud
      ? createEmptyCellCompact()
      : buildCellCompactData(
          new_cell_names_array,
          flatCoordinateArray,
          dim,
          viz_state.cats.dict_cell_cats
        );

    set_spatial_bounds_from_flat_coordinates(
      viz_state,
      flatCoordinateArray,
      dim,
      numRows
    );

    if (pointCloud) {
      set_point_cloud_cell_position_buffers(
        viz_state,
        flatCoordinateArray,
        dim,
        numRows
      );
    }

    // Build optional UMAP position buffers for cell rendering
    if (viz_state.umap.has_umap) {
      if (pointCloud) {
        set_point_cloud_umap_positions_from_names(
          viz_state,
          viz_state.cats.cell_names_array,
          numRows
        );
      } else {
        set_scatterplot_umap_positions_from_names(
          viz_state,
          viz_state.cats.cell_names_array,
          numRows
        );
      }
    } else {
      viz_state.spatial.cell_umap_scatter_positions = null;
    }

    viz_state.spatial.cell_scatter_data_objects = null;

    viz_state.spatial.center_x =
      (viz_state.spatial.x_max + viz_state.spatial.x_min) / 2;
    viz_state.spatial.center_y =
      (viz_state.spatial.y_max + viz_state.spatial.y_min) / 2;
    viz_state.spatial.data_width =
      viz_state.spatial.x_max - viz_state.spatial.x_min;
    viz_state.spatial.data_height =
      viz_state.spatial.y_max - viz_state.spatial.y_min;

    // Update cell layer with new data (clone, don't recreate)
    // Disable transitions for instant dataset switching
    refresh_cell_layer_data(layers_obj, viz_state, {
      id: `cell-layer-dataset-${new_index}`,
      transitions: false,
    });

    // Dispose of old image layers to clear any cached tile data
    if (layers_obj.image_layers && Array.isArray(layers_obj.image_layers)) {
      layers_obj.image_layers.forEach((layer) => {
        if (layer && typeof layer.finalize === 'function') {
          try {
            layer.finalize();
          } catch (e) {
            // Ignore finalize errors
            void e;
          }
        }
      });
    }

    // Create completely new image layers with unique IDs to force fresh tile fetching
    const new_image_layers = await make_image_layers(viz_state, new_index);
    layers_obj.image_layers = new_image_layers;

    // Update background layer extent if needed
    if (viz_state.dimensions) {
      layers_obj.background_layer = ini_background_layer(viz_state);
    }

    // Clear transcript and path data for the new dataset
    viz_state.genes.trx_data = [];
    viz_state.genes.trx_gene_ids = new Int32Array();
    viz_state.cats.polygon_cell_names = [];
    viz_state.combo_data.trx = [];
    viz_state.combo_data.trx_compact = createEmptyTrxCompact();
    viz_state.combo_data.cell_compact = createEmptyCellCompact();
    if (viz_state.viewport_cache) {
      viz_state.viewport_cache.visibleTileKey = null;
      viz_state.viewport_cache.lastGeneBarData = null;
      viz_state.viewport_cache.lastCellBarData = null;
    }

    layers_obj.trx_layer = layers_obj.trx_layer.clone({
      id: `trx-layer-dataset-${new_index}`,
      data: [],
    });

    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-dataset-${new_index}`,
      data: [],
    });

    // Clear cache for new dataset
    if (viz_state.cache?.cell) {
      viz_state.cache.cell.clear();
    }
    if (viz_state.cache?.trx) {
      viz_state.cache.trx.clear();
    }

    // Temporarily reset selections (will be restored below)
    viz_state.cats.selected_cats = [];
    viz_state.genes.selected_genes = [];
    viz_state.cats.cat = 'cluster';

    // Update the layers reference
    viz_state.layers_obj = layers_obj;

    // Update the current dataset index
    viz_state.obs_store.current_dataset_index.set(new_index);

    // Re-enable deck rendering
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      background_layer: true,
      image_layers: true,
      cell_layer: true,
      path_layer: true,
      trx_layer: true,
      trx_data: true,
      path_data: true,
    });

    // Force deck to update with new layers
    const layers_list = get_layers_list(
      layers_obj,
      viz_state.close_up,
      viz_state
    );
    deck_ist.setProps({ layers: layers_list });

    // Restore persistent state (selected clusters, genes, UMAP view, image visibility)
    // This allows users to compare the same selection across different datasets
    await restore_persistent_state(viz_state, layers_obj, saved_state);

    // Force deck to update with restored layers (especially if gene expression was restored)
    const final_layers_list = get_layers_list(
      viz_state.layers_obj,
      viz_state.close_up,
      viz_state
    );
    deck_ist.setProps({ layers: final_layers_list });

    // Trigger a final layer update to reflect restored state
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: false,
    });
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: true,
    });
  } finally {
    // Mark switching as complete
    viz_state.obs_store.dataset_switching.set(false);
  }
};
