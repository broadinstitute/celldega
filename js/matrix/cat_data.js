export const set_row_cat_data = (network, viz_state) => {

    var index_row = 0
    let matrix_index = 0;

    const num_row_cats = 3

    var num_points = viz_state.mat.num_rows * num_row_cats

    const row_cat_data =  new Array(num_points).fill(0).map( () => {

        var index_col = matrix_index % num_row_cats

        if (matrix_index % num_row_cats === 0){
        index_row += 1;
        }

        const p = {
            position: [viz_state.viz.row_cat_offset * (index_col + 0.5), viz_state.viz.row_offset * (index_row + 0.5)],
            color: [0, 255, 0, 255],
            name: 'something ' + index_row
        };

        matrix_index += 1;

        return p;
    })

    return row_cat_data

}

export const set_col_cat_data = (network, viz_state) => {
    const num_row_cats = 3
    var num_points = viz_state.mat.num_rows * num_row_cats

    var index_row = 0
    let matrix_index = 0;

    const col_cat_data = new Array(num_points).fill(0).map( () => {

        var index_col = matrix_index % viz_state.mat.num_cols

        if (matrix_index % viz_state.mat.num_cols === 0){
        index_row += 1;
        }

        const p = {
            position: [viz_state.viz.col_offset * (index_col + 0.5), viz_state.viz.col_cat_offset * (index_row + 0.5)],
            color: [0, 255, 0, 150],
            name: 'some column ' + index_col,
        };

        matrix_index += 1;

        return p;
    });

    return col_cat_data
}