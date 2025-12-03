import * as d3 from 'd3';

import { ini_background_layer } from '../deck-gl/layers/background_layer';
import { make_image_layers } from '../deck-gl/layers/image_layers';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import { set_cell_cats, set_dict_cell_cats } from '../global_variables/cat';
import { set_cell_names_array, set_cell_name_to_index_map } from '../global_variables/cell_names_array';
import { set_color_dict_gene } from '../global_variables/color_dict_gene';
import { options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_dimensions } from '../global_variables/image_dimensions';
import { set_image_info, set_image_layer_colors, set_image_format } from '../global_variables/image_info';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_cluster_metadata } from '../global_variables/meta_cluster';
import { set_meta_gene } from '../global_variables/meta_gene';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { get_scatter_data } from '../read_parquet/get_scatter_data';
import { scale_umap_data } from '../umap/scale_umap_data';

import { set_image_layer_sliders } from './sliders';

/**
 * Switch to a different dataset by updating layers and state without rebuilding deck.gl.
 * This approach avoids accumulating WebGL contexts.
 *
 * @param {number} newIndex - The index of the dataset to switch to
 * @param {Object} viz_state - The visualization state object
 * @param {Object} deck_ist - The deck.gl instance
 * @param {Object} layers_obj - The layers object
 */
export const switch_dataset = async (newIndex, viz_state, deck_ist, layers_obj) => {
  const base_urls = viz_state.base_urls || [];

  if (newIndex < 0 || newIndex >= base_urls.length) {
    console.error('Invalid dataset index:', newIndex);
    return;
  }

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
    const newDataset = base_urls[newIndex];
    const new_base_url = newDataset.url;

    // Update global base URL
    set_global_base_url(viz_state, new_base_url);

    // Load new landscape parameters
    await set_landscape_parameters(viz_state.img, new_base_url, viz_state.aws);

    const tmp_image_info = viz_state.img.landscape_parameters.image_info;
    const image_name_for_dim = tmp_image_info[0].name;

    // Update image format and info
    set_image_format(viz_state.img, viz_state.img.landscape_parameters.image_format);
    set_image_info(viz_state.img, tmp_image_info);
    set_image_layer_sliders(viz_state.img);
    set_image_layer_colors(viz_state.img.image_layer_colors, viz_state.img.image_info);

    // Update dimensions
    const tech = viz_state.img.landscape_parameters.technology;
    if (tech !== 'Chromium' && tech !== 'point-cloud') {
      await set_dimensions(viz_state, new_base_url, image_name_for_dim);
    }

    // Load new meta_gene data
    viz_state.genes.gene_counts = [];
    viz_state.genes.meta_gene = {};
    await set_meta_gene(viz_state.genes, new_base_url, viz_state.seg.version, viz_state.aws);
    viz_state.genes.top_gene_counts = viz_state.genes.gene_counts.slice(0, 100);

    // Update gene bar data
    viz_state.obs_store.new_gene_bar_data.set(viz_state.genes.top_gene_counts);

    // Load new color dict for genes
    await set_color_dict_gene(viz_state.genes, new_base_url, viz_state.seg.version, viz_state.aws);

    // Load new cell metadata
    let cell_url;
    if (viz_state.seg.version === 'default') {
      cell_url = `${new_base_url}/cell_metadata.parquet`;
    } else {
      cell_url = `${new_base_url}/cell_metadata_${viz_state.seg.version}.parquet`;
    }

    const cell_arrow_table = await get_arrow_table(cell_url, options.fetch, viz_state.aws);
    set_cell_names_array(viz_state.cats, cell_arrow_table);
    viz_state.spatial.cell_scatter_data = get_scatter_data(cell_arrow_table);

    set_cell_name_to_index_map(viz_state.cats);

    // Load cluster data
    if (viz_state.cats.has_meta_cell) {
      const inst_index = viz_state.cats.meta_cell_attr.indexOf(viz_state.cats.inst_cell_attr);
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

    set_dict_cell_cats(viz_state.cats);

    // Reset cluster metadata and counts
    viz_state.cats.color_dict_cluster = {};
    viz_state.cats.cluster_counts = [];
    await set_cluster_metadata(viz_state);

    // Update cell bar data
    viz_state.obs_store.new_cell_bar_data.set(viz_state.cats.cluster_counts);

    // Rebuild cell scatter data objects
    const new_cell_names_array = cell_arrow_table.getChild('name').toArray();
    const flatCoordinateArray = viz_state.spatial.cell_scatter_data.attributes.getPosition.value;
    const dim = viz_state.spatial.cell_scatter_data.attributes.getPosition.size || 2;

    // Update combo_data.cell
    viz_state.combo_data.cell = new_cell_names_array.map((name, index) => ({
      name,
      cat: viz_state.cats.dict_cell_cats[name],
      x: flatCoordinateArray[index * dim],
      y: flatCoordinateArray[index * dim + 1],
      z: dim === 3 ? flatCoordinateArray[index * dim + 2] : 0,
    }));

    // Build cell scatter data objects
    let cell_scatter_data_objects;
    if (viz_state.umap.has_umap) {
      const flatCoordinateArray_umap = new Float64Array(
        viz_state.cats.cell_names_array.flatMap((cell_id) => {
          let coords = viz_state.umap.umap[cell_id];
          if (!coords) {
            coords = [0, 0];
          }
          return coords;
        })
      );

      const numRows = viz_state.spatial.cell_scatter_data.length;
      cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
        name: viz_state.cats.cell_names_array[i],
        position:
          dim === 3
            ? [
                flatCoordinateArray[i * dim],
                flatCoordinateArray[i * dim + 1],
                flatCoordinateArray[i * dim + 2],
              ]
            : [flatCoordinateArray[i * dim], flatCoordinateArray[i * dim + 1]],
        umap: [
          flatCoordinateArray_umap[i * 2],
          flatCoordinateArray_umap[i * 2 + 1],
        ],
      }));

      cell_scatter_data_objects = scale_umap_data(viz_state, cell_scatter_data_objects);
    } else {
      const numRows = viz_state.spatial.cell_scatter_data.length;
      cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
        name: viz_state.cats.cell_names_array[i],
        position:
          dim === 3
            ? [
                flatCoordinateArray[i * dim],
                flatCoordinateArray[i * dim + 1],
                flatCoordinateArray[i * dim + 2],
              ]
            : [flatCoordinateArray[i * dim], flatCoordinateArray[i * dim + 1]],
      }));
    }

    viz_state.spatial.cell_scatter_data_objects = cell_scatter_data_objects;

    // Update spatial bounds
    viz_state.spatial.x_min = d3.min(cell_scatter_data_objects.map((d) => d.position[0]));
    viz_state.spatial.x_max = d3.max(cell_scatter_data_objects.map((d) => d.position[0]));
    viz_state.spatial.y_min = d3.min(cell_scatter_data_objects.map((d) => d.position[1]));
    viz_state.spatial.y_max = d3.max(cell_scatter_data_objects.map((d) => d.position[1]));
    if (dim === 3) {
      viz_state.spatial.z_min = d3.min(cell_scatter_data_objects.map((d) => d.position[2]));
      viz_state.spatial.z_max = d3.max(cell_scatter_data_objects.map((d) => d.position[2]));
    }

    viz_state.spatial.center_x = (viz_state.spatial.x_max + viz_state.spatial.x_min) / 2;
    viz_state.spatial.center_y = (viz_state.spatial.y_max + viz_state.spatial.y_min) / 2;
    viz_state.spatial.data_width = viz_state.spatial.x_max - viz_state.spatial.x_min;
    viz_state.spatial.data_height = viz_state.spatial.y_max - viz_state.spatial.y_min;

    // Update cell layer with new data (clone, don't recreate)
    // Disable transitions for instant dataset switching
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-dataset-${newIndex}`,
      data: cell_scatter_data_objects,
      transitions: false,
      updateTriggers: {
        getPosition: [viz_state.obs_store.umap_state.get(), newIndex],
        getFillColor: [viz_state.selection_token, newIndex],
      },
    });

    // Update image layers by creating new ones with new base_url
    const new_image_layers = await make_image_layers(viz_state);
    layers_obj.image_layers = new_image_layers;

    // Update background layer extent if needed
    if (viz_state.dimensions) {
      layers_obj.background_layer = ini_background_layer(viz_state);
    }

    // Clear transcript and path data for the new dataset
    viz_state.genes.trx_data = [];
    viz_state.genes.trx_names_array = [];
    viz_state.cats.polygon_cell_names = [];
    viz_state.combo_data.trx = [];

    layers_obj.trx_layer = layers_obj.trx_layer.clone({
      id: `trx-layer-dataset-${newIndex}`,
      data: [],
    });

    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-dataset-${newIndex}`,
      data: [],
    });

    // Clear cache for new dataset
    if (viz_state.cache?.cell) {
      viz_state.cache.cell.clear();
    }
    if (viz_state.cache?.trx) {
      viz_state.cache.trx.clear();
    }

    // Reset selections
    viz_state.cats.selected_cats = [];
    viz_state.genes.selected_genes = [];
    viz_state.obs_store.selected_cats.set([]);
    viz_state.obs_store.selected_genes.set([]);

    // Update the layers reference
    viz_state.layers_obj = layers_obj;

    // Update the current dataset index
    viz_state.obs_store.current_dataset_index.set(newIndex);

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
    const layers_list = get_layers_list(layers_obj, viz_state.close_up);
    deck_ist.setProps({ layers: layers_list });

  } catch (error) {
    console.error('Error during dataset switch:', error);
    throw error;
  } finally {
    // Mark switching as complete
    viz_state.obs_store.dataset_switching.set(false);
  }
};
