import { cat, cell_cats, selected_cats } from '../global_variables/cat'
import { cell_exp_array } from '../global_variables/cell_exp_array'
import { color_dict_cluster } from '../global_variables/meta_cluster'

// transparent to red
export const get_cell_color = (i, d) => {

    if (cat === 'cluster') {

        const inst_cat = cell_cats[d.index]

        // console.log('inst_cat', inst_cat)
        // console.log('color_dict_cluster', color_dict_cluster)

        let inst_color = color_dict_cluster[inst_cat]

        // if selected_cats is empty all cells are visible
        let inst_opacity = selected_cats.length === 0 || selected_cats.includes(inst_cat) ? 255 : 10

        // Check if inst_color is an array and log an error if it's not
        if (!Array.isArray(inst_color)) {
            inst_color = [0, 0, 0]
            inst_opacity = 50
        }

        return [...inst_color, inst_opacity]

    } else {

        // color cells based on gene expression

        const inst_exp = cell_exp_array[d.index]

        return [255, 0, 0, inst_exp]

    }
}