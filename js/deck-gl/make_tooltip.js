import { cell_names_array } from "../global_variables/cell_names_array";
import { trx_names_array } from "../global_variables/trx_names_array";
import * as d3 from 'd3'

export const make_tooltip = (info) => {

    let inst_name

    if (info.index === -1 || !info.layer) return null;

    if (info.layer.id === 'cell-layer'){
        inst_name = cell_names_array[info.index]
    } else if (info.layer.id.startsWith('trx-layer')) {
        inst_name = trx_names_array[info.index]
    }


    d3.selectAll('.deck-tooltip')
      .style('margin-top', '75px')    

    return {
        html: `<div>${inst_name}</div>`,
    }

}