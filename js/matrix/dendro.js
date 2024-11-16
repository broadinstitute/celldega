export const alt_slice_linkage = (viz_state, axis, dist_thresh) => {

    // console.log('alt_slice_linkage')

    let clust_a
    let clust_b

    let group_dict = {}

    // initialize group_links and dictionary
    viz_state[axis + '_nodes'].forEach((x, i) => {

        group_dict[i] = [i]
        x.group_links = i

    })

    // the max individual cluster id
    const max_clust_id = viz_state[axis + '_nodes'].length

    const min_dist = 0

    let new_clust_id

    viz_state.linkage[axis].forEach((x, i) => {

        if (x[2] > min_dist && x[2] < dist_thresh){

            // get cluster that are being combined together
            clust_a = x[0]
            clust_b = x[1]

            new_clust_id = max_clust_id + i

            // make new array, concat lower level cluster, delete lower level clusters
            group_dict[new_clust_id] = []
            group_dict[new_clust_id] = group_dict[new_clust_id].concat(
                group_dict[clust_a],
                group_dict[clust_b]
            )

            delete group_dict[clust_a]
            delete group_dict[clust_b]

        }

    })


    // // making dictionary of lists of clusters
    // {
    //   1: ['a', 'b', 'c'],
    //   2: ['d', 'e'],
    // }

    // // making flat dictionary of row/col to cluster
    // {
    //   'a': 1,
    //   'b': 1
    //    ...
    // }

    // Make flat dictionary
    let flat_group_dict = {}
    Object.entries(group_dict).forEach(([inst_cluster, nodes]) => {
        nodes.forEach(x => {
            flat_group_dict[x] = inst_cluster
        })
    })

    // state is being saved to the nodes under the key group_links
    viz_state[axis + '_nodes'].forEach((x, i) => {
        x.group_links = flat_group_dict[i]
    })

    // console.log(group_dict)
    // console.log(flat_group_dict)

}


export const calc_dendro_triangles = (viz_state, dendro, axis) => {

    // console.log('calc_dendro_triangles')

    var triangle_info = {}

    var inst_nodes = viz_state[axis + '_nodes']

    var heat_shift
    var heat_size
    var tri_width
    var num_labels = viz_state.mat['num_' + axis + 's'] // params.labels['num_'+axis]

    if (axis === 'row'){
      heat_size = viz_state.viz.mat_width // params.viz_dim.heat_size.y
      tri_width = heat_size/num_labels
    } else {
      heat_size = viz_state.viz.mat_height // params.viz_dim.heat_size.x
      tri_width  = heat_size/num_labels
    }

    // console.log(viz_state.mat)
    // console.log('heat_size', heat_size)
    // console.log('num_labels', num_labels)
    // console.log('tri_width', tri_width)

    var inst_order = viz_state.order.current[axis] // params.order.inst[axis]

    // console.log(inst_order)

    inst_nodes.forEach((inst_node, index)=> {

        var order_index = inst_node[inst_order]

        // new way of getting group
        ////////////////////////////////////////////
        var inst_group = inst_node.group_links

        var inst_top

        if (axis === 'row'){
            heat_shift = 0 // params.viz_dim.mat_size.y - params.viz_dim.heat_size.y
            // inst_top = -params.node_canvas_pos.y_arr[order_index] - 2 * tri_width - 2 * heat_shift

            let inst_row_index = viz_state.mat.num_rows - viz_state.mat.orders.row[inst_order][index]

            inst_top = viz_state.viz.row_offset * (inst_row_index + 1.5)

        } else {
            // emperical rule
            heat_shift = 0 // params.viz_dim.mat_size.x - params.viz_dim.heat_size.x
            // inst_top = -params.node_canvas_pos.x_arr[order_index] - 2 * tri_width + 2 * heat_shift

            let inst_col_index = viz_state.mat.num_cols - viz_state.mat.orders.col[inst_order][index]

            inst_top = viz_state.viz.col_offset * (inst_col_index + 0.5)
        }

        var inst_bot = inst_top + tri_width

        var inst_name = inst_node.name

        // not sure if this is still needed
        if (inst_name.indexOf(': ') >= 0){
            inst_name = inst_name.split(': ')[1]
        }

        // // initialize triangle info for a new group
        // if ( _.has(triangle_info, inst_group) === false ){
        //     triangle_info[inst_group] = {}
        //     triangle_info[inst_group].name_top = inst_name
        //     triangle_info[inst_group].name_bot = inst_name
        //     triangle_info[inst_group].pos_top = inst_top
        //     triangle_info[inst_group].pos_bot = inst_bot
        //     triangle_info[inst_group].pos_mid = (inst_top + inst_bot)/2
        //     triangle_info[inst_group].name = inst_group
        //     triangle_info[inst_group].all_names = []
        //     triangle_info[inst_group].axis = axis
        // }

        // // Initialize triangle info for a new group
        // if (!triangle_info.hasOwnProperty(inst_group)) {
        //     triangle_info[inst_group] = {
        //         name_top: inst_name,
        //         name_bot: inst_name,
        //         pos_top: inst_top,
        //         pos_bot: inst_bot,
        //         pos_mid: (inst_top + inst_bot) / 2,
        //         name: inst_group,
        //         all_names: [],
        //         axis: axis
        //     }
        // }

        if (!Object.prototype.hasOwnProperty.call(triangle_info, inst_group)) {
            triangle_info[inst_group] = {
                name_top: inst_name,
                name_bot: inst_name,
                pos_top: inst_top,
                pos_bot: inst_bot,
                pos_mid: (inst_top + inst_bot) / 2,
                name: inst_group,
                all_names: [],
                axis: axis
            };
        }



        triangle_info[inst_group].all_names.push(inst_name)

        // console.log(triangle_info[inst_group])

        if (inst_top < triangle_info[inst_group].pos_top){
            triangle_info[inst_group].name_top = inst_name
            triangle_info[inst_group].pos_top = inst_top
            triangle_info[inst_group].pos_mid = (inst_top + triangle_info[inst_group].pos_bot)/2
        }

        if (inst_bot > triangle_info[inst_group].pos_bot){
            triangle_info[inst_group].name_bot = inst_name
            triangle_info[inst_group].pos_bot = inst_bot
            triangle_info[inst_group].pos_mid = (triangle_info[inst_group].pos_top + inst_bot)/2
        }

    })

    var group_info = []

    // _.each(triangle_info, function(inst_triangle){
    //   group_info.push(inst_triangle)
    // })

    Object.values(triangle_info).forEach((inst_triangle) => {
        group_info.push(inst_triangle);
    });

    return group_info

  }