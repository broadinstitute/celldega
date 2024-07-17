import { cat, cell_cats } from '../global_variables/cat.js'
import { cell_exp_array } from '../global_variables/cell_exp_array.js'
import { cell_color_dict } from '../global_variables/cell_color_dict.js'


// transparent to red
export const get_cell_color = (i, d) => {

    if (cat === 'cluster') {

        const inst_cat = cell_cats[d.index]
        let inst_color = cell_color_dict[inst_cat]
        const inst_opacity = 255

        // Check if inst_color is an array and log an error if it's not
        if (!Array.isArray(inst_color)) {
            inst_color = [0, 0, 0]
        }

        return [...inst_color, inst_opacity]

    } else {

        // color cells based on gene expression

        const inst_exp = cell_exp_array[d.index]

        return [255, 0, 0, inst_exp]

    }
}