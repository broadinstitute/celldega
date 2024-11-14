export const set_col_label_data = (network, viz_state) => {

    let col_label_data = []

    console.log(viz_state.zoom)

    // let zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.rows.zoom_x)

    network.col_nodes.forEach((node) => {
        const p = {
            name: node.name,
            ini: node.ini,
            clust: node.clust,
            rank: node.rank,
            rankvar: node.rankvar,
        };
        col_label_data.push(p);
    })

    viz_state.labels.col_label_data = col_label_data

    viz_state.mat.col_orders = {}
    viz_state.mat.col_orders.ini = col_label_data.map(d => d.ini)
    viz_state.mat.col_orders.clust = col_label_data.map(d => d.clust)
    viz_state.mat.col_orders.rank = col_label_data.map(d => d.rank)
    viz_state.mat.col_orders.rankvar = col_label_data.map(d => d.rankvar)

}

export const set_row_label_data = (network, viz_state) => {

    let row_label_data = []

    network.row_nodes.forEach((node) => {
        const p = {
            name: node.name,
            ini: node.ini,
            clust: node.clust,
            rank: node.rank,
            rankvar: node.rankvar,
        };
        row_label_data.push(p);
    })

    viz_state.labels.row_label_data = row_label_data

    viz_state.mat.row_orders = {}
    viz_state.mat.row_orders.ini = row_label_data.map(d => d.ini)
    viz_state.mat.row_orders.clust = row_label_data.map(d => d.clust)
    viz_state.mat.row_orders.rank = row_label_data.map(d => d.rank)
    viz_state.mat.row_orders.rankvar = row_label_data.map(d => d.rankvar)
}