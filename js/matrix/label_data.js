export const set_col_label_data = (network, viz_state) => {

    let col_label_data = []

    let col_label_offset = 35

    console.log(viz_state.zoom)

    let zoom_factor = Math.pow(2, viz_state.zoom.zoom_data.rows.zoom_x)

    console.log(zoom_factor)

    network.col_nodes.forEach((node, index) => {
        const p = {
            position: [
                viz_state.viz.col_width * (index + 3/4),
                (viz_state.viz.col_label_height/2  + col_label_offset + zoom_factor) * zoom_factor],
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