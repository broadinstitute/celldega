/* eslint-disable import/no-cycle */

import * as d3 from 'd3';
import { ScatterplotLayer } from 'deck.gl';

import {
  set_cell_cats,
  set_dict_cell_cats,
  update_selected_cats,
  update_cat,
} from '../../global_variables/cat';
import {
  set_cell_names_array,
  set_cell_name_to_index_map,
} from '../../global_variables/cell_names_array';
import { set_color_dict_gene } from '../../global_variables/color_dict_gene';
import { options } from '../../global_variables/fetch_options';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { get_arrow_table } from '../../read_parquet/get_arrow_table';
import { get_scatter_data } from '../../read_parquet/get_scatter_data';
import { scale_umap_data } from '../../umap/scale_umap_data';
import { get_layers_list } from '../utils/layers_ist';

import { update_path_layer_id } from './path_layer';
import { update_trx_layer_id } from './trx_layer';

// // Forward declarations for functions used before definition
// export function update_cell_layer_id(layers_obj, new_cat) {
//   layers_obj.cell_layer = layers_obj.cell_layer.clone({
//     id: `cell-layer-${new_cat}`,
//   });
// }

const cell_layer_onclick = async (info, d, deck_ist, layers_obj, viz_state) => {
  // Check if the device is a touch device
  const isTouchDevice =
    'ontouchstart' in window || navigator.maxTouchPoints > 0;

  let inst_cat;

  if (isTouchDevice) {
    // Fallback on the previous method for touch devices
    inst_cat = viz_state.cats.cell_cats[info.index];
  } else {
    // Use the tooltip category for non-touch devices
    inst_cat = viz_state.tooltip_cat_cell;
  }

  update_cat(viz_state.cats, 'cluster');
  update_selected_cats(viz_state.cats, [inst_cat], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);

  const inst_cat_name = viz_state.cats.selected_cats.join('-');

  // update_cell_layer_id(layers_obj, inst_cat_name);

  if (viz_state.umap.state === false) {

    update_path_layer_id(layers_obj, inst_cat_name);
    update_trx_layer_id(viz_state.genes, layers_obj);
  }

  const layers_list = get_layers_list(layers_obj, viz_state.close_up);
  deck_ist.setProps({ layers: layers_list });

};

// transparent to red
export const get_cell_color = (cats, i, d) => {
  if (cats.cat === 'cluster') {
    try {
      const inst_cat = cats.cell_cats[d.index];

      let inst_color = cats.color_dict_cluster[inst_cat];

      let inst_opacity =
        cats.selected_cats.length === 0 || cats.selected_cats.includes(inst_cat)
          ? 255
          : 10;

      // Check if inst_color is an array and log an error if it's not
      if (!Array.isArray(inst_color)) {
        inst_color = [0, 0, 0];
        inst_opacity = 0;
      }

      return [...inst_color, inst_opacity];
    } catch {
      return [0, 0, 0, 50]; // Return a default color with some opacity to handle the error gracefully
    }
  } else {
    // color cells based on gene expression
    try {
      const inst_exp = cats.cell_exp_array[d.index]; //
      return [255, 0, 0, inst_exp];
    } catch {
      return [255, 0, 0, 50]; // Return a default color with some opacity to handle the error gracefully
    }
  }
};

export const ini_cell_layer = async (base_url, viz_state) => {

  let cell_url;
  if (viz_state.seg.version === 'default') {
    cell_url = `${base_url}/cell_metadata.parquet`;
  } else {
    cell_url = `${base_url}/cell_metadata_${viz_state.seg.version}.parquet`;
  }

  const cell_arrow_table = await get_arrow_table(
    cell_url,
    options.fetch,
    viz_state.aws
  );

  set_cell_names_array(viz_state.cats, cell_arrow_table);

  viz_state.spatial.cell_scatter_data = get_scatter_data(cell_arrow_table);

  await set_color_dict_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  set_cell_name_to_index_map(viz_state.cats);

  if (viz_state.cats.has_meta_cell) {
    viz_state.cats.cell_cats = viz_state.cats.cell_names_array.map(
      (name) => viz_state.cats.meta_cell[name]
    );
  } else {
    // default clustering

    const cluster_arrow_table = await get_arrow_table(
      `${base_url}/cell_clusters${viz_state.seg.version && viz_state.seg.version !== 'default' ? `_${viz_state.seg.version}` : ''}/cluster.parquet`,
      options.fetch,
      viz_state.aws
    );
    set_cell_cats(viz_state.cats, cluster_arrow_table, 'cluster');
  }

  set_dict_cell_cats(viz_state.cats);

  // Combine names and positions into a single array of objects
  const new_cell_names_array = cell_arrow_table.getChild('name').toArray();

  const flatCoordinateArray =
    viz_state.spatial.cell_scatter_data.attributes.getPosition.value;

  // save cell positions and categories in one place for updating cluster bar plot
  viz_state.combo_data.cell = new_cell_names_array.map((name, index) => ({
    name,
    cat: viz_state.cats.dict_cell_cats[name],
    x: flatCoordinateArray[index * 2],
    y: flatCoordinateArray[index * 2 + 1],
  }));

  let cell_scatter_data_objects;
  if (viz_state.umap.has_umap) {
    const flatCoordinateArray_umap = new Float64Array(
      viz_state.cats.cell_names_array.flatMap((cell_id) => {
        let coords;
        if (!viz_state.umap.umap[cell_id]) {
          coords = [0, 0];
        } else {
          coords = viz_state.umap.umap[cell_id];
        }

        return coords;
      })
    );

    // convert to easier to use objects
    const numRows = viz_state.spatial.cell_scatter_data.length; // Replace with arrow_table.numRows
    cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
      position: [flatCoordinateArray[i * 2], flatCoordinateArray[i * 2 + 1]],
      umap: [
        flatCoordinateArray_umap[i * 2],
        flatCoordinateArray_umap[i * 2 + 1],
      ],
    }));

    viz_state.spatial.x_min = d3.min(
      cell_scatter_data_objects.map((d) => d.position[0])
    );
    viz_state.spatial.x_max = d3.max(
      cell_scatter_data_objects.map((d) => d.position[0])
    );
    viz_state.spatial.y_min = d3.min(
      cell_scatter_data_objects.map((d) => d.position[1])
    );
    viz_state.spatial.y_max = d3.max(
      cell_scatter_data_objects.map((d) => d.position[1])
    );

    cell_scatter_data_objects = scale_umap_data(
      viz_state,
      cell_scatter_data_objects
    );
  } else {
    const numRows = viz_state.spatial.cell_scatter_data.length; // Replace with arrow_table.numRows
    cell_scatter_data_objects = Array.from({ length: numRows }, (_, i) => ({
      position: [flatCoordinateArray[i * 2], flatCoordinateArray[i * 2 + 1]],
    }));

    viz_state.spatial.x_min = d3.min(
      cell_scatter_data_objects.map((d) => d.position[0])
    );
    viz_state.spatial.x_max = d3.max(
      cell_scatter_data_objects.map((d) => d.position[0])
    );
    viz_state.spatial.y_min = d3.min(
      cell_scatter_data_objects.map((d) => d.position[1])
    );
    viz_state.spatial.y_max = d3.max(
      cell_scatter_data_objects.map((d) => d.position[1])
    );
  }

  viz_state.spatial.center_x =
    (viz_state.spatial.x_max + viz_state.spatial.x_min) / 2;
  viz_state.spatial.center_y =
    (viz_state.spatial.y_max + viz_state.spatial.y_min) / 2;

  viz_state.spatial.data_width =
    viz_state.spatial.x_max - viz_state.spatial.x_min;
  viz_state.spatial.data_height =
    viz_state.spatial.y_max - viz_state.spatial.y_min;

  // get the width of viz_state.root
  const _root_width = viz_state.root.clientWidth;
  const _root_height = viz_state.root.clientHeight;

  const canvas_width = viz_state.root.clientWidth; // 1000
  const canvas_height = viz_state.containers.root_dim.height; //500

  viz_state.spatial.scale_x = canvas_width / viz_state.spatial.data_width;
  viz_state.spatial.scale_y = canvas_height / viz_state.spatial.data_height;
  viz_state.spatial.scale = Math.min(
    viz_state.spatial.scale_x,
    viz_state.spatial.scale_y
  );

  viz_state.spatial.ini_zoom = Math.log2(viz_state.spatial.scale) * 1.01;
  viz_state.spatial.ini_x = viz_state.spatial.center_x;
  viz_state.spatial.ini_y = viz_state.spatial.center_y;

  viz_state.spatial.cell_scatter_data_objects = cell_scatter_data_objects;

  const transitions = {
    getPosition: {
      duration: 3000,
      easing: d3.easeCubic,
    },
  };

  const cell_layer = new ScatterplotLayer({
    id: 'cell-layer',
    radiusMinPixels: 1,
    getRadius: 5.0,
    pickable: true,
    getFillColor: (i, d) => get_cell_color(viz_state.cats, i, d),
    data: viz_state.spatial.cell_scatter_data_objects,
    transitions,
    getPosition: (d) => (viz_state.umap.state ? d.umap : d.position),
    updateTriggers: {
      getPosition: [viz_state.umap.state],
    },
  });

  return cell_layer;
};

export const set_cell_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    onClick: (event, d) =>
      cell_layer_onclick(event, d, deck_ist, layers_obj, viz_state),
  });
};

export const new_toggle_cell_layer_visibility = (layers_obj, visible) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    visible,
  });
};

export const update_cell_layer_radius = (layers_obj, radius) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    getRadius: radius,
  });
};

export const update_cell_pickable_state = (layers_obj, pickable) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    pickable,
  });
};

export const toggle_spatial_umap = (deck_ist, layers_obj, viz_state) => {
  layers_obj.cell_layer = layers_obj.cell_layer.clone({
    updateTriggers: {
      getPosition: [viz_state.umap.state],
    },
  });

  const layers_list = get_layers_list(layers_obj, viz_state.close_up);
  deck_ist.setProps({ layers: layers_list });
};
