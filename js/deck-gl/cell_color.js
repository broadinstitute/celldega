// transparent to red
export const get_cell_color = (cats, i, d) => {

    // console.log('cats.cat', cats.cat)

    if (cats.cat === 'cluster') {

        try {

            const inst_cat = cats.cell_cats[d.index]

            let inst_color = cats.color_dict_cluster[inst_cat]

            let inst_opacity = cats.selected_cats.length === 0 || cats.selected_cats.includes(inst_cat) ? 255 : 10

            // Check if inst_color is an array and log an error if it's not
            if (!Array.isArray(inst_color)) {
                inst_color = [0, 0, 0]
                inst_opacity = 0
            }

            // if (viz_state.z_level.inst_level !== 'all'){
            //     let inst_level = viz_state.z_level.z_level_array[d.index]

            //     if (inst_level !== viz_state.z_level.inst_level){
            //         return [0, 0, 0, 0]
            //     }
            // }

            return [...inst_color, inst_opacity]

        } catch {
            return [0, 0, 0, 50] // Return a default color with some opacity to handle the error gracefully
        }

    } else {

        // color cells based on gene expression
        // try {

            const inst_exp = cats.cell_exp_array[d.index]

            // if (viz_state.z_level.inst_level !== 'all'){
            //     let inst_level = viz_state.z_level.z_level_array[d.index]

            //     if (inst_level !== viz_state.z_level.inst_level){
            //         return [0, 0, 0, 0]
            //     }
            // }

            // if a meta_cell is available, only plot these cells
            if (cats.has_meta_cell){
                // check if the cell is in cats.meta_cell
                const inst_name = cats.cell_names_array[d.index]

                if (inst_name in cats.meta_cell === false){
                    return [0, 0, 0, 0]
                }
            }

            return [255, 0, 0, inst_exp]

        // } catch {
        //     return [255, 0, 0, 0] // Return a default color with some opacity to handle the error gracefully
        // }
    }

}
