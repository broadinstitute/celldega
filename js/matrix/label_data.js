
const index_offset = 1

export const set_col_label_data = (network, viz_state) => {

    let col_label_data = []

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
    viz_state.mat.orders.col.ini = col_label_data.map(d => d.ini )
    viz_state.mat.orders.col.clust = col_label_data.map(d => d.clust + index_offset)
    viz_state.mat.orders.col.rank = col_label_data.map(d => d.rank + index_offset)
    viz_state.mat.orders.col.rankvar = col_label_data.map(d => d.rankvar + index_offset)

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
    viz_state.mat.orders.row.ini = row_label_data.map(d => d.ini )
    viz_state.mat.orders.row.clust = row_label_data.map(d => d.clust + index_offset)
    viz_state.mat.orders.row.rank = row_label_data.map(d => d.rank + index_offset)
    viz_state.mat.orders.row.rankvar = row_label_data.map(d => d.rankvar + index_offset)
}