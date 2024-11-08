export const set_col_label_data = (network, viz_state) => {

    // col label data
    let matrix_index = 0;

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