export const alt_slice_linkage = (viz_state, axis, dist_thresh) => {
  let clust_a;
  let clust_b;

  const group_dict = {};

  // initialize group_links and dictionary
  viz_state[`${axis}_nodes`].forEach((x, i) => {
    group_dict[i] = [i];
    x.group_links = i;
  });

  // the max individual cluster id
  const max_clust_id = viz_state[`${axis}_nodes`].length;

  const min_dist = 0;

  let new_clust_id;

  viz_state.linkage[axis].forEach((x, i) => {
    if (x[2] > min_dist && x[2] < dist_thresh) {
      // get cluster that are being combined together
      clust_a = x[0];
      clust_b = x[1];

      new_clust_id = max_clust_id + i;

      // make new array, concat lower level cluster, delete lower level clusters
      group_dict[new_clust_id] = [];
      group_dict[new_clust_id] = group_dict[new_clust_id].concat(
        group_dict[clust_a],
        group_dict[clust_b]
      );

      delete group_dict[clust_a];
      delete group_dict[clust_b];
    }
  });

  // Make flat dictionary
  const flat_group_dict = {};
  Object.entries(group_dict).forEach(([inst_cluster, nodes]) => {
    nodes.forEach((x) => {
      flat_group_dict[x] = inst_cluster;
    });
  });

  // state is being saved to the nodes under the key group_links
  viz_state[`${axis}_nodes`].forEach((x, i) => {
    x.group_links = flat_group_dict[i];
  });
};

export const calc_dendro_triangles = (viz_state, axis) => {
  const triangle_info = {};

  const inst_nodes = viz_state[`${axis}_nodes`];

  // var heat_shift
  let heat_size;
  let tri_width;
  const num_labels = viz_state.mat[`num_${axis}s`]; // params.labels['num_'+axis]

  if (axis === 'row') {
    heat_size = viz_state.viz.mat_width; // params.viz_dim.heat_size.y
    tri_width = heat_size / num_labels;
  } else {
    heat_size = viz_state.viz.mat_height; // params.viz_dim.heat_size.x
    tri_width = heat_size / num_labels;
  }

  const inst_order = viz_state.order.current[axis]; // params.order.inst[axis]

  inst_nodes.forEach((inst_node, index) => {
    // var order_index = inst_node[inst_order]

    // new way of getting group
    ////////////////////////////////////////////
    const inst_group = inst_node.group_links;

    let inst_top;

    if (axis === 'row') {
      const inst_row_index =
        viz_state.mat.num_rows - viz_state.mat.orders.row[inst_order][index];

      inst_top = viz_state.viz.row_offset * (inst_row_index + 1.0);
    } else {
      const inst_col_index =
        viz_state.mat.num_cols - viz_state.mat.orders.col[inst_order][index];

      inst_top = viz_state.viz.col_offset * (inst_col_index + 0.0);
    }

    const inst_bot = inst_top + tri_width;

    let inst_name = inst_node.name;

    // not sure if this is still needed
    if (inst_name.indexOf(': ') >= 0) {
      inst_name = inst_name.split(': ')[1];
    }

    if (!Object.prototype.hasOwnProperty.call(triangle_info, inst_group)) {
      triangle_info[inst_group] = {
        name_top: inst_name,
        name_bot: inst_name,
        pos_top: inst_top,
        pos_bot: inst_bot,
        pos_mid: (inst_top + inst_bot) / 2,
        name: inst_group,
        all_names: [],
        axis,
      };
    }

    triangle_info[inst_group].all_names.push(inst_name);

    if (inst_top < triangle_info[inst_group].pos_top) {
      triangle_info[inst_group].name_top = inst_name;
      triangle_info[inst_group].pos_top = inst_top;
      triangle_info[inst_group].pos_mid =
        (inst_top + triangle_info[inst_group].pos_bot) / 2;
    }

    if (inst_bot > triangle_info[inst_group].pos_bot) {
      triangle_info[inst_group].name_bot = inst_name;
      triangle_info[inst_group].pos_bot = inst_bot;
      triangle_info[inst_group].pos_mid =
        (triangle_info[inst_group].pos_top + inst_bot) / 2;
    }
  });

  const group_info = [];

  Object.values(triangle_info).forEach((inst_triangle) => {
    group_info.push(inst_triangle);
  });

  viz_state.dendro.group_info[axis] = group_info;
};

export const ini_dendro = (viz_state) => {
  viz_state.dendro = {};

  viz_state.dendro.default_level = 5;
  viz_state.dendro.tri_height = 0.1;
  viz_state.dendro.trap_height = 0.03;
  viz_state.dendro.trap_float = 0.005;

  viz_state.dendro.dendro_args = {};
  viz_state.dendro.group_level = {};
  viz_state.dendro.polygons = {};
  viz_state.dendro.update_dendro = false;

  viz_state.dendro.selected_clust_names = [];

  viz_state.dendro.group_info = {};

  viz_state.dendro.default_link_level = 0.5;

  viz_state.dendro.output_label_format = 'list';

  viz_state.dendro.min_dist = {};
  viz_state.dendro.min_dist.row = 0; // 0.75
  viz_state.dendro.min_dist.col = 0; // 0.75

  const axes = ['col', 'row'];

  let link_mat;
  viz_state.dendro.max_linkage_dist = {};
  let dist_thresh;

  axes.forEach((axis) => {
    link_mat = viz_state.linkage[axis];
    viz_state.dendro.max_linkage_dist[axis] =
      link_mat[link_mat.length - 1][2] + 0.01;
    dist_thresh =
      viz_state.dendro.max_linkage_dist[axis] *
      viz_state.dendro.default_link_level;

    // alternate linkage slicing code
    alt_slice_linkage(viz_state, axis, dist_thresh);

    calc_dendro_triangles(viz_state, axis);
  });
};

export const calc_dendro_polygons = (viz_state, axis) => {
  viz_state.dendro.polygons[axis] = [];

  viz_state.dendro.group_info[axis].forEach((group) => {
    const { pos_top, pos_bot, pos_mid } = group;

    if (axis === 'row') {
      // Row dendrogram - right side of the heatmap, pointing outward (right)
      const height = pos_bot - pos_top; // Increase width for better visibility

      const new_pos_bot = 7;

      // Triangle vertices
      const triangle = [
        [new_pos_bot + 100, pos_mid], // Right vertex (pointing outward)
        [new_pos_bot, pos_mid - height / 2], // Top-left of the base
        [new_pos_bot, pos_mid + height / 2], // Bottom-left of the base
      ];

      viz_state.dendro.polygons[axis].push({
        coordinates: triangle,
        properties: { ...group, axis, is_active: false }, // Attach group data and axis
      });
    } else if (axis === 'col') {
      const height = pos_bot - pos_top; // Increase width for better visibility

      // const new_pos_bot = -1000
      const new_pos_bot = 17;

      // Triangle vertices
      // higher y value is lower on the screen
      const triangle = [
        [pos_mid, new_pos_bot + 100], // Right vertex (pointing outward)
        [pos_mid - height / 2, new_pos_bot], // Top-left of the base
        [pos_mid + height / 2, new_pos_bot], // Bottom-left of the base
      ];

      viz_state.dendro.polygons[axis].push({
        coordinates: triangle,
        properties: { ...group, axis, is_active: false }, // Attach group data and axis
      });
    }
  });
};
