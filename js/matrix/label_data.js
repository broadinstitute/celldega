export const set_col_label_data = (network, viz_state) => {

    let col_label_data = []

    console.log(viz_state.zoom)

    network.col_nodes.forEach((node, index) => {

        const p = {
            name: node.name,
            ini: node.ini,
            clust: node.clust,
            rank: node.rank,
            rankvar: node.rankvar,
            index: index
        };
        col_label_data.push(p);
    })

    viz_state.labels.col_label_data = col_label_data

    viz_state.labels.clicks.col = 0

    viz_state.mat.orders.col = {}
    viz_state.mat.orders.col.ini = col_label_data.map(d => d.ini)
    viz_state.mat.orders.col.clust = col_label_data.map(d => d.clust)
    viz_state.mat.orders.col.rank = col_label_data.map(d => d.rank)
    viz_state.mat.orders.col.rankvar = col_label_data.map(d => d.rankvar)

}

export const set_row_label_data = (network, viz_state) => {

    let row_label_data = []

    network.row_nodes.forEach((node, index) => {
        const p = {
            name: node.name,
            ini: node.ini,
            clust: node.clust,
            rank: node.rank,
            rankvar: node.rankvar,
            index: index
        };
        row_label_data.push(p);
    })

    viz_state.labels.row_label_data = row_label_data
    viz_state.labels.clicks.row = 0

    viz_state.mat.orders.row = {}
    viz_state.mat.orders.row.ini = row_label_data.map(d => d.ini)
    viz_state.mat.orders.row.clust = row_label_data.map(d => d.clust)
    viz_state.mat.orders.row.rank = row_label_data.map(d => d.rank)
    viz_state.mat.orders.row.rankvar = row_label_data.map(d => d.rankvar)
}