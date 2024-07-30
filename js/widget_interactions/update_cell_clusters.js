import { model } from '../global_variables/model'
import { update_meta_cluster } from '../global_variables/meta_cluster'
import { update_cell_cats } from '../global_variables/cat'

export const update_cell_clusters = () => {
    const new_cluster_info = model.get('cell_clusters')
    console.log('New cell clusters just received:', new_cluster_info)

    update_meta_cluster(new_cluster_info['meta_cluster'])

    update_cell_cats(new_cluster_info['new_clusters'])

    // Process the newClusters JSON blob as needed
    // Update the visualization with the new cluster data
}
