import * as d3 from 'd3'
import { trx_names_array } from "../global_variables/trx_names_array"
import { polygon_cell_names } from "../vector_tile/polygons/grab_cell_tiles_in_view"

export const make_tooltip = (viz_state, info) => {

    if (info.index === -1 || !info.layer) return null;

    let inst_html = ''
    let inst_name = ''
    let inst_cat = ''

    if (info.layer.id.startsWith('cell-layer') || info.layer.id.startsWith('path-layer')) {
        inst_name = info.layer.id.startsWith('cell-layer') ? viz_state.cats.cell_names_array[info.index] : polygon_cell_names[info.index]
        inst_cat = viz_state.cats.dict_cell_cats[inst_name]
        inst_html = `<div>cell: ${inst_name}</div><div>cluster: ${inst_cat}</div>`

        viz_state.tooltip_cat_cell = inst_cat

    } else if (info.layer.id.startsWith('trx-layer')) {
        inst_name = trx_names_array[info.index]
        inst_html = `<div>transcript: ${inst_name}</div>`
    }

    d3.selectAll('.deck-tooltip')
      .style('margin-top', '75px')

    return {
        html: inst_html,
    }

}