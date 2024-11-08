export const set_col_label_data = (network, viz_state) => {

    let col_label_data = []
    network.col_nodes.forEach((node, index) => {
        const p = {
            position: [viz_state.viz.col_width * (index + 3/4), viz_state.viz.col_label_height/2],
            name: node.name
        };
        col_label_data.push(p);
    })

    return col_label_data

}

export const set_row_label_data = (network, viz_state) => {
    let row_label_data = []
    network.row_nodes.forEach((node, index) => {
        const p = {
            position: [
                viz_state.viz.row_label_width / 2,
                viz_state.viz.row_offset * (index + 1.5)
              ],
            name: node.name
        };
        row_label_data.push(p);
    })

    return row_label_data
}