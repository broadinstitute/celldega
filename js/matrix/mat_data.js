export const set_mat_data = (network, viz_state) => {

    // Iterate over each row and column in network.mat
    let inst_color
    network.mat.forEach((rowArray, index_row) => {
        rowArray.forEach((tile_value, index_col) => {

            if (tile_value >= 0){
                inst_color = [255, 0, 0]
            } else {
                inst_color = [0, 0, 255]
            }

            const p = {
                position: [
                    viz_state.viz.col_offset * (index_col + 0.5),
                    viz_state.viz.row_offset * (index_row + 1.5)
                ],
                color: [inst_color[0], inst_color[1], inst_color[2], 255 * Math.abs(tile_value) / viz_state.mat.max_abs_value],
                value: tile_value,
                row: index_row,
                col: index_col,
            };
            viz_state.mat.mat_data.push(p);
        });
    });

}