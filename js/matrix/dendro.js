export const alt_slice_linkage = (viz_state, axis, dist_thresh) => {

    console.log('alt_slice_linkage')

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

            // // replace cluster ids with new cluster id - effectively merging clusters
            // network[axis + '_nodes'].forEach((x, i) => {
            //   if (x.group_links == clust_a || x.group_links == clust_b){
            //     x.group_links = new_clust_id
            //   }
            // })

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
