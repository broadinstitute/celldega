import { get_arrow_table } from '../read_parquet/get_arrow_table';
import {
  getRowKeyArray,
  getTableColumnArray,
} from '../read_parquet/table_accessors';
import { hexToRgb } from '../utils/hexToRgb';

import { options } from './fetch_options';

export const update_meta_cluster = (cats, new_meta_cluster) => {
  cats.color_dict_cluster = {};

  for (const cluster_name in new_meta_cluster.color) {
    cats.color_dict_cluster[String(cluster_name)] =
      new_meta_cluster.color[cluster_name];
  }

  // convert each hexcode color value to rgb
  for (const cluster_name in cats.color_dict_cluster) {
    cats.color_dict_cluster[cluster_name] = hexToRgb(
      cats.color_dict_cluster[cluster_name]
    );
  }

  const cluster_counts_ini = new_meta_cluster.count;

  // convert cluster_counts_ini into an array of objects with values name and value
  cats.cluster_counts = [];
  for (const cluster_name in cluster_counts_ini) {
    cats.cluster_counts.push({
      name: String(cluster_name),
      value: cluster_counts_ini[cluster_name],
    });
  }

  cats.cluster_counts.sort((a, b) => b.value - a.value);
};

export const set_cluster_metadata = async (viz_state) => {
  if (viz_state.cats.has_meta_cluster) {
    // find the index of color in viz_state.cats.meta_cluster_attr
    const color_index = viz_state.cats.meta_cluster_attr.indexOf('color');

    // loop through the keys of meta_cluster and assemble a dictionary of colors use a map or something functional
    for (const cluster_name in viz_state.cats.meta_cluster) {
      viz_state.cats.color_dict_cluster[String(cluster_name)] = hexToRgb(
        viz_state.cats.meta_cluster[cluster_name][color_index] || '#000000'
      );
    }

    // find the index of count in viz_state.cats.meta_cluster_attr
    const count_index = viz_state.cats.meta_cluster_attr.indexOf('count');

    for (const cluster_name in viz_state.cats.meta_cluster) {
      const raw = viz_state.cats.meta_cluster[cluster_name][count_index];
      const value = raw !== undefined ? Number(raw) : 0;

      viz_state.cats.cluster_counts.push({
        name: String(cluster_name),
        value,
      });
    }
  } else {
    let meta_cell_url;

    if (viz_state.seg.version === 'default') {
      meta_cell_url = `${viz_state.global_base_url}/cell_clusters/meta_cluster.parquet`;
    } else {
      meta_cell_url = `${viz_state.global_base_url}/cell_clusters_${viz_state.seg.version}/meta_cluster.parquet`;
    }

    const meta_cell_arrow_table = await get_arrow_table(
      meta_cell_url,
      options.fetch,
      viz_state.aws
    );

    let cluster_names = getRowKeyArray(meta_cell_arrow_table, [
      'cluster',
      'leiden',
      '__index_level_0__',
      'index',
    ]);
    const colors = getTableColumnArray(meta_cell_arrow_table, 'color');
    const counts = getTableColumnArray(meta_cell_arrow_table, 'count');

    if (cluster_names.length !== colors.length) {
      cluster_names = colors.map((_color, index) => String(index));
    }

    cluster_names.forEach((cluster_name, index) => {
      viz_state.cats.color_dict_cluster[String(cluster_name)] = hexToRgb(
        colors[index]
      );

      viz_state.cats.cluster_counts.push({
        name: String(cluster_name),
        value: Number(counts[index] ?? 0),
      });
    });
  }

  viz_state.cats.cluster_counts.sort((a, b) => b.value - a.value);
};
